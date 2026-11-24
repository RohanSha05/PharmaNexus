from datetime import timedelta
from django.test import TestCase,Client
from django.contrib.auth.models import User,Group
from django.db import connection,transaction,DatabaseError
from django.utils import timezone
from django.core.exceptions import ValidationError
from .models import *
from .services.fefo_engine import deduct,approve
from .services.potency_sourcing import adjusted_api
from .services.ai_forecast_intel import forecast
from .services.reporting import workbook
class WorkflowTests(TestCase):
 def setUp(self):
  self.user=User.objects.create_user('manager',password='test-password')
  self.user.groups.add(Group.objects.create(name='Manager'))
  self.sku=SKU.objects.create(name='Product',molecule='API',category='Fever',unit_price=20,unit_cost=8)
  self.a=Depot.objects.create(name='Sylhet');self.b=Depot.objects.create(name='Chattogram')
  self.early=StockLot.objects.create(sku=self.sku,depot=self.a,batch_code='EARLY',quantity=100,expiry_date=timezone.localdate()+timedelta(days=10))
  self.late=StockLot.objects.create(sku=self.sku,depot=self.a,batch_code='LATE',quantity=200,expiry_date=timezone.localdate()+timedelta(days=30))
  self.client.force_login(self.user)
 def test_potency(self): self.assertAlmostEqual(adjusted_api(100,95),105.2632)
 def test_invalid_potency(self):
  for p in [0,-1,101]:
   with self.assertRaises(ValueError): adjusted_api(100,p)
 def test_fefo_spans_lots(self):
  r=deduct(self.sku.id,self.a.id,150,self.user,'Customer order')
  self.assertEqual([x['quantity'] for x in r],[100,50]);self.early.refresh_from_db();self.late.refresh_from_db();self.assertEqual(self.early.quantity,0);self.assertEqual(self.late.quantity,150);self.assertEqual(AuditTrail.objects.count(),2)
 def test_insufficient_stock_rolls_back(self):
  with self.assertRaises(ValueError): deduct(self.sku.id,self.a.id,301,self.user,'Customer order')
  self.early.refresh_from_db();self.assertEqual(self.early.quantity,100);self.assertEqual(AuditTrail.objects.count(),0)
 def test_expired_excluded(self):
  self.early.expiry_date=timezone.localdate();self.early.save()
  r=deduct(self.sku.id,self.a.id,50,self.user,'Customer order');self.assertEqual(r[0]['lot'],'LATE')
 def test_reason_rolls_back(self):
  with self.assertRaises(ValueError): deduct(self.sku.id,self.a.id,50,self.user,' ')
  self.early.refresh_from_db();self.assertEqual(self.early.quantity,100)
 def test_transfer_conserves_stock_and_rejects_replay(self):
  t=Transfer.objects.create(lot=self.early,destination=self.b,quantity=60,estimated_margin=100)
  approve(t.pk,self.user,'Balance demand')
  self.assertEqual(sum(StockLot.objects.values_list('quantity',flat=True)),300)
  with self.assertRaises(ValueError): approve(t.pk,self.user,'Replay')
  self.assertEqual(sum(StockLot.objects.values_list('quantity',flat=True)),300)
 def test_failed_transfer_rolls_back(self):
  t=Transfer.objects.create(lot=self.early,destination=self.b,quantity=101,estimated_margin=100)
  with self.assertRaises(ValueError): approve(t.pk,self.user,'Balance demand')
  t.refresh_from_db();self.assertEqual(t.status,'pending');self.assertFalse(StockLot.objects.filter(depot=self.b).exists())
 def test_audit_orm_protected(self):
  a=AuditTrail.objects.create(actor=self.user,action='Test',entity='Test',reason='Testing')
  with self.assertRaises(ValidationError): a.delete()
  with self.assertRaises(ValidationError): AuditTrail.objects.filter(pk=a.pk).update(reason='Rewrite')
 def test_audit_database_protected(self):
  a=AuditTrail.objects.create(actor=self.user,action='Test',entity='Test',reason='Testing')
  for sql in ['DELETE FROM core_audittrail WHERE id=%s',"UPDATE core_audittrail SET reason='rewrite' WHERE id=%s"]:
   with self.assertRaises(DatabaseError):
    with transaction.atomic():
     with connection.cursor() as c: c.execute(sql,[a.id])
 def test_anonymous_denied(self):
  self.client.logout();self.assertEqual(self.client.get('/api/state/').status_code,403)
 def test_rbac_denies_warehouse_approval(self):
  self.user.groups.clear();self.user.groups.add(Group.objects.create(name='Warehouse'))
  self.assertEqual(self.client.post('/api/transfers/1/approve/',{'reason':'Testing'},content_type='application/json').status_code,403)
 def test_csrf_enforced(self):
  c=Client(enforce_csrf_checks=True);c.force_login(self.user)
  self.assertEqual(c.post('/api/deduct/',{'sku':self.sku.id,'depot':self.a.id,'quantity':1,'reason':'Test'},content_type='application/json').status_code,403)
 def test_invalid_quantity(self):
  r=self.client.post('/api/deduct/',{'sku':self.sku.id,'depot':self.a.id,'quantity':-1,'reason':'Test'},content_type='application/json');self.assertEqual(r.status_code,400)
 def test_batch_api(self):
  data={'sku':self.sku.id,'date':str(timezone.localdate()),'machine':'MX-01','shift':'Day','standard_api':100,'potency_pct':98,'planned_units':100,'actual_units':98,'waste_cost_bdt':24,'reason':'Batch completed'}
  self.assertEqual(self.client.post('/api/production/',data,content_type='application/json').status_code,201);self.assertEqual(AuditTrail.objects.count(),1)
 def test_excel(self):
  from openpyxl import load_workbook
  from io import BytesIO
  wb=load_workbook(BytesIO(workbook()));self.assertEqual(len(wb.sheetnames),8);self.assertIn('Audit',wb.sheetnames)
 def test_forecast_horizon_and_validation(self):
  today=timezone.localdate()
  DemandObservation.objects.bulk_create([DemandObservation(sku=self.sku,depot=self.a,date=today-timedelta(days=120-i),units=100+i%7*5,holiday=i%30==0) for i in range(120)])
  f=forecast(self.sku.id,self.a.id);self.assertEqual(len(f['daily']),90);self.assertEqual(f['total'],sum(r['units'] for r in f['daily']));self.assertGreaterEqual(f['mae'],0);self.assertAlmostEqual(sum(x['importance'] for x in f['importance']),100,delta=.5)
 def test_all_pages(self):
  for p in ['/','/forecast/','/sourcing/','/production/','/inventory/','/audit/']: self.assertEqual(self.client.get(p).status_code,200)

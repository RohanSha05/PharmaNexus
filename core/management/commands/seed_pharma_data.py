import os,random,calendar
from datetime import timedelta
from django.core.management.base import BaseCommand,CommandError
from django.contrib.auth.models import User,Group
from django.db import transaction
from django.utils import timezone
from core.models import *
class Command(BaseCommand):
 help='Create deterministic synthetic data spanning 24 months; refuses to overwrite existing demand.'
 @transaction.atomic
 def handle(self,*args,**options):
  if DemandObservation.objects.exists(): raise CommandError('Data already exists. Use a new database; this command never overwrites records.')
  rng=random.Random(42); today=timezone.localdate(); end=today-timedelta(days=1); start=end.replace(year=end.year-2,day=min(end.day,28))+timedelta(days=1)
  password=os.getenv('PHARMA_DEMO_PASSWORD')
  if not password or len(password)<12: raise CommandError('Set PHARMA_DEMO_PASSWORD (at least 12 characters) before seeding.')
  for role in ['Manager','Analyst','Warehouse','Production','Auditor']: Group.objects.get_or_create(name=role)
  for name,role in [('manager','Manager'),('analyst','Analyst'),('warehouse','Warehouse'),('production','Production'),('auditor','Auditor')]:
   u,created=User.objects.get_or_create(username=name)
   if created: u.set_password(password); u.save(); u.groups.add(Group.objects.get(name=role))
  depots=[Depot.objects.create(name=n) for n in ['Dhaka','Chattogram','Sylhet','Rajshahi','Khulna']]
  names=[('Paracetamol 500 mg','Paracetamol','Fever'),('ORS sachet','ORS','Gastro'),('Cetirizine 10 mg','Cetirizine','Respiratory'),('Amoxicillin 500 mg','Amoxicillin','Respiratory'),('Omeprazole 20 mg','Omeprazole','Gastro'),('Metformin 500 mg','Metformin','Chronic'),('Amlodipine 5 mg','Amlodipine','Chronic'),('Azithromycin 500 mg','Azithromycin','Respiratory'),('Zinc 20 mg','Zinc','Gastro'),('Salbutamol inhaler','Salbutamol','Respiratory'),('Vitamin C 250 mg','Ascorbic acid','Supplement'),('Losartan 50 mg','Losartan','Chronic'),('Montelukast 10 mg','Montelukast','Respiratory'),('Pantoprazole 40 mg','Pantoprazole','Gastro'),('Vitamin D3 2000 IU','Cholecalciferol','Supplement')]
  skus=[SKU.objects.create(name=n,molecule=m,category=c,unit_price=20+i*4,unit_cost=8+i*2) for i,(n,m,c) in enumerate(names)]
  observations=[]
  for si,sku in enumerate(skus):
   for di,depot in enumerate(depots):
    for j in range((end-start).days+1):
     d=start+timedelta(days=j); seasonal=1.5 if (sku.category=='Fever' and d.month in [6,7,8,9]) or (sku.category=='Respiratory' and d.month in [11,12,1,2]) or (sku.category=='Gastro' and d.month in [4,5,6,7]) else 1
     # Synthetic holiday windows only: not a verified religious calendar.
     holiday=(d.month==3 and 20<=d.day<=25) or (d.month==10 and 10<=d.day<=13) or (d.month==12 and d.day==16)
     rx=1-.0005*j if si==7 else 1+.0001*j; base=(110+si*9)*(1-di*.12); reg=.9 if si==7 and j>650 else 1
     units=max(0,round(base*seasonal*rx*reg*(1.3 if holiday else 1)*(.88 if d.weekday() in [4,5] else 1)+rng.gauss(0,9)))
     observations.append(DemandObservation(sku=sku,depot=depot,date=d,units=units,rx_index=rx,disease_index=seasonal,holiday=holiday,regulatory_index=reg,competitor_price=round(.95+rng.random()*.1,3)))
  DemandObservation.objects.bulk_create(observations,batch_size=500)
  for sku in skus:
   for depot in depots:
    for k in range(2): StockLot.objects.create(sku=sku,depot=depot,batch_code=f'PN-{sku.id:02}-{depot.id}-{k}',expiry_date=today+timedelta(days=40 if k==0 else 210),quantity=3500 if k==0 else 8500)
  StockLot.objects.filter(sku=skus[0],depot=depots[2]).update(quantity=0)
  StockLot.objects.filter(sku=skus[0],depot=depots[2],expiry_date=today+timedelta(days=40)).update(quantity=16000)
  StockLot.objects.filter(sku=skus[0],depot=depots[1]).update(quantity=0)
  for i in range(240):
   night=i%3==0; spike=night and i%4==0
   planned=10000; actual=int(planned*(rng.uniform(.81,.87) if spike else rng.uniform(.96,.99)))
   ProductionBatch.objects.create(sku=skus[i%15],date=today-timedelta(days=i//4),machine='MX-03' if spike else f'MX-0{1+i%3}',shift='Night' if night else 'Day',standard_api=100,potency_pct=round(rng.uniform(92,99),2),planned_units=planned,actual_units=actual,waste_cost_bdt=(planned-actual)*12)
  for country,supplier,price,freight,purity,lead in [('India','Aster Chemicals',980,130,99,18),('China','SinoPure Ingredients',850,170,89,24),('Italy','Milano Pharma',1110,190,99.8,35),('Spain','Iberia Actives',1080,180,98.5,32),('South Korea','HanBio Materials',1030,160,99.2,27)]: SupplierOffer.objects.create(country=country,supplier=supplier,molecule='Paracetamol',nominal_price=price,freight_duty=freight,potency_pct=purity,lead_days=lead)
  for c,p in [('India',18),('Vietnam',19),('Kenya',24),('Sri Lanka',22),('Philippines',21)]: ExportBenchmark.objects.create(country=c,product='Paracetamol 500 mg',unit_price_bdt=p)
  AuditTrail.objects.create(actor=User.objects.get(username='manager'),action='Synthetic dataset seeded',entity='Dataset',old_json={},new_json={'demand_rows':len(observations)},reason='Initial portfolio demonstration dataset')
  self.stdout.write(self.style.SUCCESS(f'Seeded {len(observations):,} demand observations, 15 SKUs, 5 depots and 240 batches. Users: manager, analyst, warehouse, production, auditor.'))

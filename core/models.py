from django.db import models
from django.core.exceptions import ValidationError
from django.conf import settings
from django.db.models import Q
class SKU(models.Model):
 name=models.CharField(max_length=100); molecule=models.CharField(max_length=100); category=models.CharField(max_length=40)
 unit_price=models.DecimalField(max_digits=12,decimal_places=2); unit_cost=models.DecimalField(max_digits=12,decimal_places=2)
class Depot(models.Model):
 name=models.CharField(max_length=60,unique=True)
class SupplierOffer(models.Model):
 supplier=models.CharField(max_length=100); country=models.CharField(max_length=40); molecule=models.CharField(max_length=100)
 nominal_price=models.FloatField(); freight_duty=models.FloatField(); potency_pct=models.FloatField(); lead_days=models.PositiveIntegerField()
 @property
 def landed_cost(self): return self.nominal_price+self.freight_duty
 @property
 def true_cost(self): return self.landed_cost*100/self.potency_pct
class ProductionBatch(models.Model):
 sku=models.ForeignKey(SKU,on_delete=models.PROTECT); date=models.DateField(); machine=models.CharField(max_length=30); shift=models.CharField(max_length=20)
 standard_api=models.FloatField(); potency_pct=models.FloatField(); planned_units=models.PositiveIntegerField(); actual_units=models.PositiveIntegerField(); waste_cost_bdt=models.FloatField()
 @property
 def yield_pct(self): return round(self.actual_units/self.planned_units*100,2)
class DemandObservation(models.Model):
 sku=models.ForeignKey(SKU,on_delete=models.PROTECT); depot=models.ForeignKey(Depot,on_delete=models.PROTECT); date=models.DateField()
 units=models.PositiveIntegerField(); rx_index=models.FloatField(default=1); disease_index=models.FloatField(default=1); holiday=models.BooleanField(default=False); regulatory_index=models.FloatField(default=1); competitor_price=models.FloatField(default=1)
 class Meta:
  constraints=[models.UniqueConstraint(fields=['sku','depot','date'],name='unique_daily_demand')]
  indexes=[models.Index(fields=['date','sku','depot'])]
class StockLot(models.Model):
 sku=models.ForeignKey(SKU,on_delete=models.PROTECT); depot=models.ForeignKey(Depot,on_delete=models.PROTECT); batch_code=models.CharField(max_length=80); expiry_date=models.DateField(); quantity=models.PositiveIntegerField()
 class Meta:
  constraints=[models.UniqueConstraint(fields=['sku','depot','batch_code'],name='unique_depot_batch'),models.CheckConstraint(condition=Q(quantity__gte=0),name='positive_stock')]
  indexes=[models.Index(fields=['sku','depot','expiry_date'])]
class Transfer(models.Model):
 lot=models.ForeignKey(StockLot,on_delete=models.PROTECT); destination=models.ForeignKey(Depot,on_delete=models.PROTECT); quantity=models.PositiveIntegerField(); estimated_margin=models.FloatField(); status=models.CharField(max_length=20,default='pending'); created_at=models.DateTimeField(auto_now_add=True)
class ExportBenchmark(models.Model):
 country=models.CharField(max_length=50); product=models.CharField(max_length=100); unit_price_bdt=models.FloatField(); note=models.CharField(max_length=200,default='Synthetic benchmark; not a market quote')
class AuditQuerySet(models.QuerySet):
 def update(self,**kwargs): raise ValidationError('Audit entries are append-only')
 def delete(self): raise ValidationError('Audit entries are append-only')
class AuditTrail(models.Model):
 actor=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.PROTECT); action=models.CharField(max_length=80); entity=models.CharField(max_length=100); old_json=models.JSONField(default=dict); new_json=models.JSONField(default=dict); reason=models.TextField(); timestamp_utc=models.DateTimeField(auto_now_add=True)
 objects=AuditQuerySet.as_manager()
 def save(self,*args,**kwargs):
  if self.pk: raise ValidationError('Audit entries are append-only')
  if not self.reason.strip(): raise ValidationError('A reason is required')
  return super().save(*args,**kwargs)
 def delete(self,*args,**kwargs): raise ValidationError('Audit entries are append-only')

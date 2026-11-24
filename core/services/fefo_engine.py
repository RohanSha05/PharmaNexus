from django.db import transaction
from django.db.models import F,Sum
from django.utils import timezone
from core.models import StockLot,Transfer,AuditTrail
from .ai_forecast_intel import forecast

def audit(user,action,entity,old,new,reason):
 if not reason or not reason.strip(): raise ValueError('A reason is required')
 AuditTrail.objects.create(actor=user,action=action,entity=entity,old_json=old,new_json=new,reason=reason)
@transaction.atomic
def deduct(sku,depot,quantity,user,reason):
 if not isinstance(quantity,int) or quantity<=0: raise ValueError('Quantity must be a positive integer')
 lots=list(StockLot.objects.select_for_update().filter(sku_id=sku,depot_id=depot,expiry_date__gt=timezone.localdate(),quantity__gt=0).order_by('expiry_date','id'))
 if sum(l.quantity for l in lots)<quantity: raise ValueError('Insufficient unexpired stock')
 remaining=quantity; allocations=[]
 for lot in lots:
  take=min(remaining,lot.quantity)
  if not take: break
  old=lot.quantity
  if StockLot.objects.filter(pk=lot.pk,quantity__gte=take).update(quantity=F('quantity')-take)!=1: raise ValueError('Stock changed; retry the request')
  allocations.append({'lot':lot.batch_code,'quantity':take,'expiry':str(lot.expiry_date)})
  audit(user,'FEFO deduction',f'StockLot:{lot.pk}',{'quantity':old},{'quantity':old-take},reason)
  remaining-=take
 return allocations
@transaction.atomic
def approve(transfer_id,user,reason):
 t=Transfer.objects.select_for_update().select_related('lot').get(pk=transfer_id)
 if t.status!='pending': raise ValueError('This transfer was already processed')
 lot=StockLot.objects.select_for_update().get(pk=t.lot_id)
 if lot.expiry_date<=timezone.localdate(): raise ValueError('Expired stock cannot be transferred')
 if t.destination_id==lot.depot_id: raise ValueError('Destination must differ from source')
 if StockLot.objects.filter(pk=lot.pk,quantity__gte=t.quantity).update(quantity=F('quantity')-t.quantity)!=1: raise ValueError('Insufficient source stock')
 target,created=StockLot.objects.get_or_create(sku=lot.sku,depot=t.destination,batch_code=lot.batch_code,defaults={'expiry_date':lot.expiry_date,'quantity':0})
 if target.expiry_date!=lot.expiry_date: raise ValueError('Batch expiry mismatch')
 StockLot.objects.filter(pk=target.pk).update(quantity=F('quantity')+t.quantity)
 if Transfer.objects.filter(pk=t.pk,status='pending').update(status='approved')!=1: raise ValueError('Transfer already processed')
 audit(user,'Transfer approved',f'Transfer:{t.pk}',{'status':'pending','source_quantity':lot.quantity,'destination_quantity':target.quantity},{'status':'approved','quantity':t.quantity,'source_quantity':lot.quantity-t.quantity,'destination_quantity':target.quantity+t.quantity},reason)
 return t.pk
@transaction.atomic
def recommend(user,reason):
 from core.models import Depot
 created=[]; today=timezone.localdate(); cache={}
 def demand(sku,depot,days):
  key=(sku,depot)
  if key not in cache: cache[key]=forecast(sku,depot)['daily']
  return sum(r['units'] for r in cache[key][:days])
 for lot in StockLot.objects.select_related('sku','depot').filter(expiry_date__gt=today,expiry_date__lte=today+__import__('datetime').timedelta(days=90),quantity__gt=0):
  if Transfer.objects.filter(lot=lot,status='pending').exists(): continue
  days=(lot.expiry_date-today).days
  earlier=StockLot.objects.filter(sku=lot.sku,depot=lot.depot,expiry_date__gt=today,expiry_date__lt=lot.expiry_date).aggregate(q=Sum('quantity'))['q'] or 0
  source_need=max(0,demand(lot.sku_id,lot.depot_id,days)-earlier)
  excess=max(0,lot.quantity-source_need)
  for depot in Depot.objects.exclude(pk=lot.depot_id):
   if not excess: break
   stock=StockLot.objects.filter(sku=lot.sku,depot=depot,expiry_date__gt=today).aggregate(q=Sum('quantity'))['q'] or 0
   inbound=Transfer.objects.filter(lot__sku=lot.sku,destination=depot,status='pending').aggregate(q=Sum('quantity'))['q'] or 0
   need=max(0,demand(lot.sku_id,depot.id,max(0,days-2))-stock-inbound)
   qty=int(min(excess,need)); margin=qty*(float(lot.sku.unit_price-lot.sku.unit_cost)-2)-500
   if qty>0 and margin>0:
    t=Transfer.objects.create(lot=lot,destination=depot,quantity=qty,estimated_margin=round(margin,2)); created.append(t.id); excess-=qty
    audit(user,'Transfer proposed',f'Transfer:{t.id}',{}, {'quantity':qty,'margin':round(margin,2)},reason)
 return created

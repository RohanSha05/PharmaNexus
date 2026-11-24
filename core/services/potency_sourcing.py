from sklearn.ensemble import IsolationForest
from core.models import ProductionBatch,SupplierOffer
def adjusted_api(standard,potency):
 if standard<=0 or not 0<potency<=100: raise ValueError('API must be positive; potency must be above 0 and at most 100%')
 return round(standard*100/potency,4)
def sourcing():
 return sorted([{'id':o.id,'supplier':o.supplier,'country':o.country,'molecule':o.molecule,'nominal':o.nominal_price,'landed':o.landed_cost,'potency':o.potency_pct,'true_cost':round(o.true_cost,2),'lead_days':o.lead_days} for o in SupplierOffer.objects.all()],key=lambda x:x['true_cost'])
def production():
 batches=list(ProductionBatch.objects.select_related('sku').order_by('-date','-id')[:500])
 if not batches: return []
 X=[[b.waste_cost_bdt/b.planned_units,b.yield_pct,int(b.shift=='Night'),int(b.machine=='MX-03')] for b in batches]
 labels=IsolationForest(contamination=.10,random_state=42).fit_predict(X) if len(X)>10 else [1]*len(X)
 return [{'id':b.id,'sku':b.sku.name,'date':str(b.date),'machine':b.machine,'shift':b.shift,'yield':b.yield_pct,'waste':b.waste_cost_bdt,'potency':b.potency_pct,'adjusted_api':adjusted_api(b.standard_api,b.potency_pct),'anomaly':bool(label==-1)} for b,label in zip(batches,labels)]

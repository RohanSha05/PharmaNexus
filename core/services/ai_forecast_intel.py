import calendar
from datetime import timedelta
import numpy as np
import pandas as pd
from django.utils import timezone
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error
from core.models import DemandObservation
FEATURES=['month','weekday','weekend','holiday','disease_index','rx_index','regulatory_index','competitor_price','trend']
def forecast(sku,depot,rx=1.,regulatory=1.,competitor=1.,holiday_dates=None):
 rows=list(DemandObservation.objects.filter(sku_id=sku,depot_id=depot).order_by('date').values())
 if len(rows)<90: raise ValueError('At least 90 daily observations are needed')
 df=pd.DataFrame(rows); dates=pd.to_datetime(df.date); origin=dates.min()
 df['month']=dates.dt.month; df['weekday']=dates.dt.weekday; df['weekend']=(df.weekday>=4)&(df.weekday<=5); df['trend']=(dates-origin).dt.days
 split=len(df)-30
 model=RandomForestRegressor(n_estimators=60,max_depth=10,min_samples_leaf=3,random_state=42,n_jobs=1)
 model.fit(df.iloc[:split][FEATURES],df.iloc[:split].units)
 mae=float(mean_absolute_error(df.iloc[split:].units,model.predict(df.iloc[split:][FEATURES])))
 model.fit(df[FEATURES],df.units)
 start=max(rows[-1]['date'],timezone.localdate()); future=[]; holiday_dates=set(holiday_dates or [])
 for i in range(1,91):
  d=start+timedelta(days=i)
  seasonal=df[df.month==d.month]
  disease=float(seasonal.disease_index.mean()) if len(seasonal) else 1
  future.append({'date':str(d),'month':d.month,'weekday':d.weekday(),'weekend':d.weekday() in [4,5],'holiday':str(d) in holiday_dates,'disease_index':disease,'rx_index':float(df.rx_index.tail(30).mean())*rx,'regulatory_index':regulatory,'competitor_price':competitor,'trend':(pd.Timestamp(d)-origin).days})
 pred=model.predict(pd.DataFrame(future)[FEATURES]); daily=[{'date':r['date'],'units':max(0,round(float(p)))} for r,p in zip(future,pred)]
 end=rows[-1]['date']; prevmonth=(end.replace(day=1)-timedelta(days=1)); ly=end.year-1
 def total(a,b): return sum(r['units'] for r in rows if a<=r['date']<=b)
 def compare(a,b): return {'current':a,'previous':b,'change_pct':round((a-b)/b*100,1) if b else None}
 month_start=end.replace(day=1); prior_end=prevmonth.replace(day=min(end.day,calendar.monthrange(prevmonth.year,prevmonth.month)[1])); sply_end=end.replace(year=ly,day=min(end.day,calendar.monthrange(ly,end.month)[1]))
 return {'daily':daily,'total':sum(x['units'] for x in daily),'mae':round(mae,2),'training_rows':len(rows),'as_of':str(end),'importance':sorted([{'feature':k,'importance':round(float(v)*100,1)} for k,v in zip(FEATURES,model.feature_importances_)],key=lambda v:-v['importance']),'wow':compare(total(end-timedelta(days=6),end),total(end-timedelta(days=13),end-timedelta(days=7))),'mom':compare(total(month_start,end),total(prevmonth.replace(day=1),prior_end)),'sply':compare(total(month_start,end),total(sply_end.replace(day=1),sply_end)),'patterns':{'weekday_mean':round(float(df[~df.weekend].units.mean()),1),'weekend_mean':round(float(df[df.weekend].units.mean()),1),'holiday_mean':round(float(df[df.holiday].units.mean()),1) if df.holiday.any() else None},'history':[{'date':str(r['date']),'units':r['units']} for r in rows[-90:]],'assumptions':'Scenario inputs, not live external feeds. Bangladesh weekend: Friday/Saturday. Holiday dates are user supplied. No causal interpretation of feature importance.'}

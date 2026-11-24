import json
from django.http import HttpResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from .models import *
from .serializers import *
from .rbac import roles
from .services.potency_sourcing import sourcing,production,adjusted_api
from .services.ai_forecast_intel import forecast
from .services.fefo_engine import deduct,approve,recommend,audit
from .services.reporting import workbook
@login_required
@ensure_csrf_cookie
def page(request): return render(request,'app.html')
def validate(cls,data):
 s=cls(data=data); s.is_valid(raise_exception=True); return s.validated_data
def safe(fn,*args,**kwargs):
 try: return fn(*args,**kwargs)
 except (ValueError,SKU.DoesNotExist,Depot.DoesNotExist,Transfer.DoesNotExist) as e: raise ValidationError(str(e))
@api_view(['GET'])
def state(request):
 today=timezone.localdate()
 stocks=[{'id':s.id,'sku_id':s.sku_id,'sku':s.sku.name,'depot_id':s.depot_id,'depot':s.depot.name,'batch':s.batch_code,'expiry':str(s.expiry_date),'days':(s.expiry_date-today).days,'quantity':s.quantity,'value':float(s.sku.unit_price)*s.quantity} for s in StockLot.objects.select_related('sku','depot')]
 transfers=[{'id':t.id,'sku':t.lot.sku.name,'source':t.lot.depot.name,'destination':t.destination.name,'quantity':t.quantity,'margin':t.estimated_margin,'status':t.status,'lot':t.lot_id} for t in Transfer.objects.select_related('lot__sku','lot__depot','destination').order_by('-id')]
 history=list(DemandObservation.objects.values('date').annotate(units=Sum('units')).order_by('-date')[:90])[::-1]
 return Response({'user':request.user.username,'roles':list(request.user.groups.values_list('name',flat=True)),'admin':request.user.is_superuser,'skus':list(SKU.objects.values()),'depots':list(Depot.objects.values()),'sourcing':sourcing(),'production':production(),'stocks':stocks,'transfers':transfers,'benchmarks':list(ExportBenchmark.objects.values()),'history':history,'row_count':DemandObservation.objects.count(),'audit':[{'id':a.id,'actor':a.actor.username if a.actor else 'System','action':a.action,'entity':a.entity,'old':a.old_json,'new':a.new_json,'reason':a.reason,'timestamp':a.timestamp_utc.isoformat()} for a in AuditTrail.objects.select_related('actor').order_by('-id')[:200]]})
@api_view(['POST'])
def potency(request):
 d=validate(PotencySerializer,request.data); return Response({'adjusted':safe(adjusted_api,d['standard'],d['potency'])})
@api_view(['POST'])
@roles('Analyst','Manager')
def prediction(request):
 d=validate(ForecastSerializer,request.data); d['holiday_dates']=[str(x) for x in d['holiday_dates']]; return Response(safe(forecast,**d))
@api_view(['POST'])
@roles('Warehouse','Manager')
def deduction(request):
 d=validate(DeductSerializer,request.data); return Response({'allocations':safe(deduct,user=request.user,**d)})
@api_view(['POST'])
@roles('Manager')
def approval(request,pk):
 d=validate(ReasonSerializer,request.data); return Response({'id':safe(approve,pk,request.user,d['reason'])})
@api_view(['POST'])
@roles('Manager','Analyst')
def recommendations(request):
 d=validate(ReasonSerializer,request.data); return Response({'created':safe(recommend,request.user,d['reason'])})
@api_view(['POST'])
@roles('Production','Manager')
@transaction.atomic
def batch(request):
 d=validate(BatchSerializer,request.data); reason=d.pop('reason'); sku=d.pop('sku')
 if not SKU.objects.filter(pk=sku).exists(): raise ValidationError('Unknown SKU')
 b=ProductionBatch.objects.create(sku_id=sku,**d); audit(request.user,'Batch recorded',f'ProductionBatch:{b.pk}',{},json.loads(json.dumps(d,default=str)),reason); return Response({'id':b.pk},status=201)
@api_view(['GET'])
@roles('Manager','Analyst','Auditor')
def export(request):
 response=HttpResponse(workbook(),content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'); response['Content-Disposition']='attachment; filename="PharmaNexus-Report.xlsx"'; return response

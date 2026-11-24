from django.urls import path,include
from core import views as v
urlpatterns=[path('accounts/',include('django.contrib.auth.urls')),path('api/state/',v.state),path('api/potency/',v.potency),path('api/forecast/',v.prediction),path('api/deduct/',v.deduction),path('api/transfers/<int:pk>/approve/',v.approval),path('api/recommend/',v.recommendations),path('api/production/',v.batch),path('api/export/',v.export)]
urlpatterns += [path(p,v.page) for p in ['', 'forecast/','sourcing/','production/','inventory/','audit/']]

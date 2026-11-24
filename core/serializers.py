from rest_framework import serializers
class ReasonSerializer(serializers.Serializer):
 reason=serializers.CharField(min_length=3,max_length=1000,trim_whitespace=True)
class DeductSerializer(ReasonSerializer):
 sku=serializers.IntegerField(min_value=1); depot=serializers.IntegerField(min_value=1); quantity=serializers.IntegerField(min_value=1)
class PotencySerializer(serializers.Serializer):
 standard=serializers.FloatField(min_value=0.000001); potency=serializers.FloatField(min_value=0.000001,max_value=100)
class ForecastSerializer(serializers.Serializer):
 sku=serializers.IntegerField(min_value=1); depot=serializers.IntegerField(min_value=1)
 rx=serializers.FloatField(min_value=.2,max_value=2,default=1); regulatory=serializers.FloatField(min_value=.2,max_value=2,default=1); competitor=serializers.FloatField(min_value=.2,max_value=2,default=1)
 holiday_dates=serializers.ListField(child=serializers.DateField(),default=list)
class BatchSerializer(ReasonSerializer):
 sku=serializers.IntegerField(min_value=1); date=serializers.DateField(); machine=serializers.ChoiceField(choices=['MX-01','MX-02','MX-03']); shift=serializers.ChoiceField(choices=['Day','Night']); standard_api=serializers.FloatField(min_value=.001); potency_pct=serializers.FloatField(min_value=.001,max_value=100); planned_units=serializers.IntegerField(min_value=1); actual_units=serializers.IntegerField(min_value=0); waste_cost_bdt=serializers.FloatField(min_value=0)
 def validate(self,data):
  if data['actual_units']>data['planned_units']: raise serializers.ValidationError('Actual units cannot exceed planned units')
  return data

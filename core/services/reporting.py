from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font,PatternFill
from core.models import SKU,Depot,StockLot,ProductionBatch,DemandObservation,AuditTrail,Transfer
from .potency_sourcing import sourcing

def workbook():
 wb=Workbook(); wb.remove(wb.active)
 datasets={'Sourcing':sourcing(),'Stock':list(StockLot.objects.values()),'Production':list(ProductionBatch.objects.values()),'Demand':list(DemandObservation.objects.values()),'Transfers':list(Transfer.objects.values()),'Audit':list(AuditTrail.objects.values()),'SKU':list(SKU.objects.values()),'Depots':list(Depot.objects.values())}
 for title,rows in datasets.items():
  ws=wb.create_sheet(title)
  if not rows: ws.append(['No records']); continue
  ws.append(list(rows[0]))
  for cell in ws[1]: cell.font=Font(color='FFFFFF',bold=True); cell.fill=PatternFill('solid',fgColor='123B3A')
  for row in rows:
   values=[]
   for value in row.values():
    if isinstance(value,(dict,list)): value=__import__('json').dumps(value)
    if getattr(value,'tzinfo',None): value=value.isoformat()
    if isinstance(value,str) and value.startswith(('=','+','-','@')): value="'"+value
    values.append(value)
   ws.append(values)
  ws.freeze_panes='A2'; ws.auto_filter.ref=ws.dimensions
  for column in ws.columns: ws.column_dimensions[column[0].column_letter].width=24
 out=BytesIO(); wb.save(out); return out.getvalue()

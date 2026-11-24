from django.db import migrations

def protect(apps,schema_editor):
 vendor=schema_editor.connection.vendor
 if vendor=='sqlite':
  schema_editor.execute("CREATE TRIGGER audit_no_update BEFORE UPDATE ON core_audittrail BEGIN SELECT RAISE(ABORT, 'Audit entries are append-only'); END;")
  schema_editor.execute("CREATE TRIGGER audit_no_delete BEFORE DELETE ON core_audittrail BEGIN SELECT RAISE(ABORT, 'Audit entries are append-only'); END;")
 elif vendor=='microsoft':
  schema_editor.execute("CREATE TRIGGER audit_no_modify ON core_audittrail INSTEAD OF UPDATE, DELETE AS BEGIN THROW 50001, 'Audit entries are append-only', 1; END;")

def unprotect(apps,schema_editor):
 for name in (['audit_no_update','audit_no_delete'] if schema_editor.connection.vendor=='sqlite' else ['audit_no_modify']): schema_editor.execute('DROP TRIGGER IF EXISTS '+name)
class Migration(migrations.Migration):
 dependencies=[('core','0001_initial')]
 operations=[migrations.RunPython(protect,unprotect)]

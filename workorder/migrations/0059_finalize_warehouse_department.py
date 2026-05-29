from django.db import migrations


def finalize_warehouse_department(apps, schema_editor):
    Department = apps.get_model("workorder", "Department")
    UserProfile = apps.get_model("workorder", "UserProfile")
    WorkOrderProcess = apps.get_model("workorder", "WorkOrderProcess")
    WorkOrderTask = apps.get_model("workorder", "WorkOrderTask")
    TaskAssignmentRule = apps.get_model("workorder", "TaskAssignmentRule")

    logistics = Department.objects.filter(code="logistics").first()
    warehouse = Department.objects.filter(code="warehouse").first()

    if logistics and not warehouse:
        logistics.code = "warehouse"
        logistics.name = "仓储物流部"
        logistics.sort_order = 12
        logistics.is_active = True
        logistics.parent = None
        logistics.save(
            update_fields=["code", "name", "sort_order", "is_active", "parent"]
        )
        warehouse = logistics
    else:
        warehouse, _ = Department.objects.update_or_create(
            code="warehouse",
            defaults={
                "name": "仓储物流部",
                "sort_order": 12,
                "is_active": True,
                "parent": None,
            },
        )
    if logistics and logistics.pk != warehouse.pk:
        for profile in UserProfile.objects.filter(departments=logistics):
            profile.departments.remove(logistics)
            profile.departments.add(warehouse)
        WorkOrderProcess.objects.filter(department=logistics).update(
            department=warehouse
        )
        WorkOrderTask.objects.filter(assigned_department=logistics).update(
            assigned_department=warehouse
        )
        for rule in TaskAssignmentRule.objects.filter(department=logistics):
            if TaskAssignmentRule.objects.filter(
                process=rule.process,
                department=warehouse,
            ).exists():
                rule.delete()
            else:
                rule.department = warehouse
                rule.save(update_fields=["department"])
        warehouse.processes.add(*logistics.processes.all())
        logistics.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("workorder", "0058_align_role_department_presets"),
    ]

    operations = [
        migrations.RunPython(finalize_warehouse_department, migrations.RunPython.noop),
    ]

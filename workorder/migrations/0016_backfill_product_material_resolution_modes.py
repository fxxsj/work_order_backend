from django.db import migrations


def forward(apps, schema_editor):
    ProductMaterial = apps.get_model("workorder", "ProductMaterial")
    WorkOrderMaterial = apps.get_model("workorder", "WorkOrderMaterial")

    product_requirements = ProductMaterial.objects.filter(
        material__specification_level="requirement"
    )
    product_requirements.filter(material__material_type="paper").update(
        calculation_mode="sheet_imposition",
        preparation_mode="pending",
        planning_required=True,
        need_cutting=False,
    )
    product_requirements.exclude(material__material_type="paper").update(
        calculation_mode="specification_selection",
        preparation_mode="pending",
        planning_required=True,
        need_cutting=False,
    )

    unresolved_work_order_items = WorkOrderMaterial.objects.filter(
        material__specification_level="requirement",
        calculation_mode="fixed",
        planning_status="not_required",
        work_order__approval_status="draft",
    )
    unresolved_work_order_items.filter(material__material_type="paper").update(
        calculation_mode="sheet_imposition",
        preparation_mode="pending",
        planning_required=True,
        planning_status="draft",
    )
    unresolved_work_order_items.exclude(material__material_type="paper").update(
        calculation_mode="specification_selection",
        preparation_mode="pending",
        planning_required=True,
        planning_status="draft",
    )


def reverse(apps, schema_editor):
    ProductMaterial = apps.get_model("workorder", "ProductMaterial")
    WorkOrderMaterial = apps.get_model("workorder", "WorkOrderMaterial")

    ProductMaterial.objects.filter(preparation_mode="pending").update(
        calculation_mode="fixed",
        preparation_mode="direct",
        planning_required=False,
        need_cutting=False,
    )
    WorkOrderMaterial.objects.filter(preparation_mode="pending").update(
        calculation_mode="fixed",
        preparation_mode="direct",
        planning_required=False,
        planning_status="not_required",
    )


class Migration(migrations.Migration):
    dependencies = [
        ("workorder", "0015_material_deferred_resolution_modes"),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]

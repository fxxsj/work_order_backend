import pytest

from workorder.models.assets import Artwork, Die, FoilingPlate, EmbossingPlate
from workorder.models.core import WorkOrderMaterial
from workorder.models.materials import Material
from workorder.tests.factories import WorkOrderFactory


@pytest.mark.django_db
def test_workorder_material_update_blocked():
    workorder = WorkOrderFactory(processes=0)
    material = Material.objects.create(name="M1", code="M001")
    WorkOrderMaterial.objects.create(work_order=workorder, material=material)

    with pytest.raises(RuntimeError):
        WorkOrderMaterial.objects.filter(work_order=workorder).update(notes="x")


@pytest.mark.django_db
def test_artwork_update_blocked():
    Artwork.objects.create(name="A1")
    with pytest.raises(RuntimeError):
        Artwork.objects.update(name="A2")


@pytest.mark.django_db
def test_die_update_blocked():
    Die.objects.create(name="D1")
    with pytest.raises(RuntimeError):
        Die.objects.update(name="D2")


@pytest.mark.django_db
def test_foiling_plate_update_blocked():
    FoilingPlate.objects.create(name="F1")
    with pytest.raises(RuntimeError):
        FoilingPlate.objects.update(name="F2")


@pytest.mark.django_db
def test_embossing_plate_update_blocked():
    EmbossingPlate.objects.create(name="E1")
    with pytest.raises(RuntimeError):
        EmbossingPlate.objects.update(name="E2")

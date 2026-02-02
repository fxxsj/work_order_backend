"""Factory Boy definitions for base models"""
import factory
from workorder.models.base import Department, Process


class DepartmentFactory(factory.django.DjangoModelFactory):
    """Factory for Department model"""

    class Meta:
        model = Department
        django_get_or_create = ('code',)

    name = factory.Sequence(lambda n: f"Department {n}")
    code = factory.Sequence(lambda n: f"DEPT{n:03d}")
    is_active = True
    sort_order = 0


class ProcessFactory(factory.django.DjangoModelFactory):
    """Factory for Process model"""

    class Meta:
        model = Process
        django_get_or_create = ('code',)

    name = factory.Sequence(lambda n: f"Process {n}")
    code = factory.Sequence(lambda n: f"PROC{n:03d}")
    is_builtin = False
    is_active = True
    is_parallel = False
    sort_order = 0
    task_generation_rule = 'general'

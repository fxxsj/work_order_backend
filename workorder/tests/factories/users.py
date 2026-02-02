"""Factory Boy definitions for User model"""
import factory
from django.contrib.auth import get_user_model
from .base import DepartmentFactory

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    """Factory for User model with UserProfile support"""

    class Meta:
        model = User
        django_get_or_create = ('username',)

    username = factory.Sequence(lambda n: f"user_{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@example.com")
    first_name = factory.Faker('first_name', locale='zh_CN')
    last_name = factory.Faker('last_name', locale='zh_CN')
    is_staff = True
    is_active = True

    # Post-generation: add to department
    @factory.post_generation
    def departments(self, create, extracted, **kwargs):
        """Add user to departments after creation"""
        if not create:
            return

        if extracted:
            # If departments provided, add user to them
            from workorder.models import UserProfile
            profile, _ = UserProfile.objects.get_or_create(user=self)
            profile.departments.set(extracted)
        elif kwargs.get('auto_department', True):
            # Auto-create a department if requested
            from workorder.models import UserProfile
            dept = DepartmentFactory()
            profile, _ = UserProfile.objects.get_or_create(user=self)
            profile.departments.add(dept)

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Use create_user for password hashing"""
        password = kwargs.pop('password', None)
        user = model_class(**kwargs)
        if password:
            user.set_password(password)
        else:
            user.set_password('test_pass_123')
        user.save()
        return user

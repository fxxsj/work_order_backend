import importlib.util
import re
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.test import SimpleTestCase
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from workorder.urls import router


PROJECT_ROOT = Path(__file__).resolve().parents[3]
FLUTTER_SRC = PROJECT_ROOT / "flutter" / "lib" / "src"
ROLE_MATRIX_PATH = (
    PROJECT_ROOT
    / "backend"
    / "workorder"
    / "permissions"
    / "role_matrix.py"
)


def _load_role_matrix():
    spec = importlib.util.spec_from_file_location("role_matrix_0055", ROLE_MATRIX_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _model_name(model_name):
    return apps.get_model("workorder", model_name)._meta.model_name


def _role_permissions_from_source():
    matrix = _load_role_matrix()
    role_permissions = {}
    for role_code, model_actions in matrix.ROLE_PERMISSIONS.items():
        permissions = set()
        for model_name, actions in model_actions.items():
            model_perm_name = _model_name(model_name)
            for action in actions:
                permissions.add(f"workorder.{action}_{model_perm_name}")
        for codenames in matrix.ROLE_CUSTOM_PERMISSIONS.get(role_code, {}).values():
            for codename in codenames:
                permissions.add(f"workorder.{codename}")
        role_permissions[role_code] = permissions
    return role_permissions


def _flutter_permission_literals():
    permissions = set()
    for path in FLUTTER_SRC.rglob("*.dart"):
        text = path.read_text(encoding="utf-8")
        permissions.update(
            match.group(0).strip("'\"")
            for match in re.finditer(r"['\"]workorder\.[a-z_]+?['\"]", text)
        )
    return permissions


class PermissionMatrixTest(SimpleTestCase):
    def test_flutter_permissions_are_covered_by_role_matrix(self):
        role_permissions = _role_permissions_from_source()
        covered_permissions = set().union(*role_permissions.values())

        missing_permissions = sorted(
            _flutter_permission_literals() - covered_permissions
        )

        self.assertEqual(missing_permissions, [])

    def test_default_permission_class_requires_authentication(self):
        self.assertEqual(
            settings.REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"],
            ["rest_framework.permissions.IsAuthenticated"],
        )

    def test_registered_viewsets_do_not_use_anonymous_readonly_permissions(self):
        offenders = []
        for prefix, viewset, _basename in router.registry:
            if IsAuthenticatedOrReadOnly in getattr(viewset, "permission_classes", []):
                offenders.append(f"{prefix}: {viewset.__name__}")

        self.assertEqual(offenders, [])

"""版类资产 API 测试。"""

from django.test import TestCase

from .conftest import APITestCaseMixin, TestDataFactory
from ..models.assets import (
    Die,
    DieProduct,
    EmbossingPlate,
    EmbossingPlateProduct,
    FoilingPlate,
    FoilingPlateProduct,
)


class PlateAssetAPITest(APITestCaseMixin, TestCase):
    """覆盖刀模、烫金版、压凸版共用序列化器的创建与更新。"""

    def setUp(self):
        super().setUp()
        self.user = TestDataFactory.create_user(
            username="plate_admin",
            is_superuser=True,
        )
        self.product = TestDataFactory.create_product(code="PLATE-P001")

    def _assert_create_and_update(
        self,
        url,
        payload,
        model,
        relation_model,
        relation_field,
    ):
        create_response = self.api_post(url, payload, user=self.user)

        self.assertEqual(create_response.status_code, 201)
        data = create_response.data["data"]
        self.assertTrue(data["code"])
        self.assertEqual(data["name"], payload["name"])

        obj = model.objects.get(id=data["id"])
        self.assertEqual(
            relation_model.objects.filter(**{relation_field: obj}).count(),
            1,
        )

        update_payload = {
            **payload,
            "name": f"{payload['name']}-更新",
            "products_data": [
                {
                    **payload["products_data"][0],
                    "quantity": 2,
                },
            ],
        }
        update_response = self.api_put(
            f"{url}{obj.id}/", update_payload, user=self.user
        )

        self.assertEqual(update_response.status_code, 200)
        obj.refresh_from_db()
        self.assertEqual(obj.name, update_payload["name"])
        relation = relation_model.objects.get(**{relation_field: obj})
        self.assertEqual(relation.quantity, 2)

    def test_create_and_update_die(self):
        self._assert_create_and_update(
            "/api/v1/dies/",
            {
                "name": "测试刀模",
                "die_type": "dedicated",
                "products_data": [
                    {
                        "product": self.product.id,
                        "quantity": 1,
                        "relation_type": "exclusive",
                    },
                ],
            },
            Die,
            DieProduct,
            "die",
        )

    def test_create_and_update_foiling_plate(self):
        self._assert_create_and_update(
            "/api/v1/foiling-plates/",
            {
                "name": "测试烫金版",
                "foiling_type": "gold",
                "products_data": [
                    {
                        "product": self.product.id,
                        "quantity": 1,
                    },
                ],
            },
            FoilingPlate,
            FoilingPlateProduct,
            "foiling_plate",
        )

    def test_create_and_update_embossing_plate(self):
        self._assert_create_and_update(
            "/api/v1/embossing-plates/",
            {
                "name": "测试压凸版",
                "products_data": [
                    {
                        "product": self.product.id,
                        "quantity": 1,
                    },
                ],
            },
            EmbossingPlate,
            EmbossingPlateProduct,
            "embossing_plate",
        )

from django.test import TestCase
from rest_framework.test import APIClient
from django.contrib.auth.models import User
from unittest.mock import MagicMock
from products.views import _rank_products


def make_product(product_name, category, tags=None, description=""):
    p = MagicMock()
    p.product_name = product_name
    p.category = category
    p.tags = tags or []
    p.product_description = description
    return p


class RankProductsTest(TestCase):

    def test_smartphone_category_tier1(self):
        products = [
            make_product("Galaxy S24", "Smartphones"),
            make_product("iPhone 15", "Smartphones"),
        ]
        ranked = _rank_products(products, "smartphone")
        for item in ranked:
            self.assertGreaterEqual(item["relevance_score"], 0.7)

    def test_charger_smartphone_tag_tier2(self):
        charger = make_product("USB-C Charger", "Accessories", tags=["smartphone", "charging"])
        ranked = _rank_products([charger], "smartphone")
        self.assertEqual(len(ranked), 1)
        score = ranked[0]["relevance_score"]
        self.assertGreaterEqual(score, 0.4)
        self.assertLess(score, 0.7)

    def test_tier1_before_tier2(self):
        tier1 = make_product("Galaxy S24", "Smartphones")
        tier2 = make_product("USB-C Charger", "Accessories", tags=["smartphone"])
        ranked = _rank_products([tier2, tier1], "smartphone")
        self.assertGreaterEqual(ranked[0]["relevance_score"], 0.7)
        self.assertLess(ranked[-1]["relevance_score"], 0.7)


class AuthEndpointsTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser",
            password="correctpassword123",
            email="test@example.com"
        )

    def test_login_wrong_password_returns_401(self):
        response = self.client.post("/api/auth/login/", {
            "username": "testuser",
            "password": "wrongpassword"
        }, format="json")
        self.assertEqual(response.status_code, 401)

    def test_register_valid_data_returns_201(self):
     response = self.client.post("/api/auth/register/", {
        "username": "newuser",
        "password": "newpass123",
        "password2": "newpass123",
        "email": "new@example.com"
     }, format="json")
     self.assertEqual(response.status_code, 201)
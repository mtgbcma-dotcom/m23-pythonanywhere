import base64

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from ..models import Category, Order, Product


class OrderTokenAuthenticationTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.password = "senha-de-teste-modulo17"
        cls.staff = get_user_model().objects.create_user(
            username="gestor", password=cls.password, is_staff=True
        )
        cls.customer = get_user_model().objects.create_user(
            username="cliente", password=cls.password
        )
        cls.staff_token = Token.objects.create(user=cls.staff)
        cls.customer_token = Token.objects.create(user=cls.customer)
        cls.category = Category.objects.create(name="Programação")
        cls.product = Product.objects.create(name="Python", price="89.90", category=cls.category)
        for _ in range(6):
            order = Order.objects.create(user=cls.customer)
            order.products.add(cls.product)
        cls.order = Order.objects.order_by("pk").first()

    def authenticate_with_token(self, token=None):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token or self.staff_token.key}")

    def test_credentials_return_token_and_repeated_login_reuses_it(self):
        for _ in range(2):
            response = self.client.post(reverse("api-token-auth"), {
                "username": "gestor", "password": self.password
            }, format="json")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data, {"token": self.staff_token.key})
        self.assertEqual(Token.objects.filter(user=self.staff).count(), 1)

    def test_wrong_password_does_not_issue_token(self):
        user = get_user_model().objects.create_user(username="sem_token", password=self.password)
        response = self.client.post(reverse("api-token-auth"), {
            "username": user.username, "password": "senha-incorreta"
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Token.objects.filter(user=user).exists())

    def test_missing_login_fields_are_rejected(self):
        for payload in [{}, {"username": "gestor"}, {"password": self.password}]:
            with self.subTest(payload=list(payload)):
                response = self.client.post(reverse("api-token-auth"), payload, format="json")
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_inactive_user_cannot_obtain_token(self):
        user = get_user_model().objects.create_user(username="inativo", password=self.password, is_active=False)
        response = self.client.post(reverse("api-token-auth"), {
            "username": user.username, "password": self.password
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Token.objects.filter(user=user).exists())

    def test_orders_without_token_return_401(self):
        response = self.client.get(reverse("api:order-list"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response["WWW-Authenticate"], "Token")

    def test_invalid_token_returns_401(self):
        self.authenticate_with_token("0" * 40)
        response = self.client.get(reverse("api:order-list"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_malformed_headers_do_not_authenticate(self):
        for header in ["Token", "Token chave extra", f"Bearer {self.staff_token.key}"]:
            with self.subTest(header_type=header.split()[0]):
                self.client.credentials(HTTP_AUTHORIZATION=header)
                self.assertEqual(self.client.get(reverse("api:order-list")).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_session_login_alone_does_not_authenticate_orders(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("api:order-list"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_basic_authentication_alone_does_not_authenticate_orders(self):
        credentials = base64.b64encode(f"gestor:{self.password}".encode()).decode()
        self.client.credentials(HTTP_AUTHORIZATION=f"Basic {credentials}")
        response = self.client.get(reverse("api:order-list"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_deleted_token_is_not_accepted(self):
        key = self.staff_token.key
        self.staff_token.delete()
        self.authenticate_with_token(key)
        response = self.client.get(reverse("api:order-list"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_inactive_user_token_is_not_accepted(self):
        self.staff.is_active = False
        self.staff.save(update_fields=["is_active"])
        self.authenticate_with_token()
        self.assertEqual(self.client.get(reverse("api:order-list")).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_valid_staff_token_lists_orders_with_pagination(self):
        self.authenticate_with_token()
        response = self.client.get(reverse("api:order-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 6)
        self.assertEqual(len(response.data["results"]), 5)
        self.assertIn("page=2", response.data["next"])
        self.assertNotIn(self.staff_token.key, str(response.data))

    def test_regular_user_token_keeps_staff_permission_requirement(self):
        self.authenticate_with_token(self.customer_token.key)
        response = self.client.get(reverse("api:order-list"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_valid_token_creates_order(self):
        self.authenticate_with_token()
        response = self.client.post(reverse("api:order-list"), {
            "user": self.customer.pk, "product_ids": [self.product.pk], "status": "pending"
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        order = Order.objects.get(pk=response.data["id"])
        self.assertEqual(order.user, self.customer)
        self.assertEqual(list(order.products.all()), [self.product])

    def test_valid_token_retrieves_order(self):
        self.authenticate_with_token()
        response = self.client.get(reverse("api:order-detail", args=[self.order.pk]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.order.pk)
        self.assertEqual(response.data["products"][0]["category"]["id"], self.category.pk)

    def test_valid_token_updates_order_with_put(self):
        self.authenticate_with_token()
        response = self.client.put(reverse("api:order-detail", args=[self.order.pk]), {
            "user": self.customer.pk, "product_ids": [self.product.pk], "status": "completed"
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "completed")

    def test_valid_token_updates_order_with_patch(self):
        self.authenticate_with_token()
        response = self.client.patch(reverse("api:order-detail", args=[self.order.pk]), {
            "status": "cancelled"
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "cancelled")

    def test_valid_token_deletes_order(self):
        self.authenticate_with_token()
        response = self.client.delete(reverse("api:order-detail", args=[self.order.pk]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Order.objects.filter(pk=self.order.pk).exists())

    def test_all_order_write_operations_require_token(self):
        url = reverse("api:order-detail", args=[self.order.pk])
        count = Order.objects.count()
        requests = [
            (self.client.post, reverse("api:order-list")),
            (self.client.put, url), (self.client.patch, url), (self.client.delete, url),
        ]
        for method, endpoint in requests:
            with self.subTest(method=method.__name__):
                response = method(endpoint, {}, format="json")
                self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(Order.objects.count(), count)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "pending")

    def test_categories_and_products_still_accept_session_login(self):
        self.client.force_login(self.staff)
        for resource in ["category", "product"]:
            with self.subTest(resource=resource):
                response = self.client.get(reverse(f"api:{resource}-list"))
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertIn("results", response.data)

    def test_token_does_not_enable_token_authentication_on_catalog(self):
        self.authenticate_with_token()
        self.assertEqual(
            self.client.get(reverse("api:category-list")).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        # Product reads are public; the token header does not grant write access.
        self.assertEqual(
            self.client.get(reverse("api:product-list")).status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            self.client.post(reverse("api:product-list"), {}, format="json").status_code,
            status.HTTP_403_FORBIDDEN,
        )

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APIRequestFactory, force_authenticate

from ..models import Category, Order, Product
from ..views import CategoryViewSet


class ViewSetTestBase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_user(username="gestor", is_staff=True)
        cls.customer = get_user_model().objects.create_user(username="cliente")
        cls.category = Category.objects.create(name="Programação")
        cls.other_category = Category.objects.create(name="Engenharia")
        cls.product = Product.objects.create(name="Python", price="89.90", category=cls.category)
        cls.other_product = Product.objects.create(name="Django", price="99.90", category=cls.category)
        cls.order = Order.objects.create(user=cls.customer)
        cls.order.products.add(cls.product)

    def setUp(self):
        self.client.force_authenticate(user=self.staff)


class CategoryViewSetTests(ViewSetTestBase):
    def test_list_returns_categories(self):
        response = self.client.get(reverse("api:category-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual({item["id"] for item in response.data["results"]}, {self.category.pk, self.other_category.pk})

    def test_retrieve_returns_correct_category(self):
        response = self.client.get(reverse("api:category-detail", args=[self.category.pk]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Programação")

    def test_create_persists_valid_category(self):
        response = self.client.post(reverse("api:category-list"), {"name": "Literatura"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Category.objects.get(pk=response.data["id"]).name, "Literatura")

    def test_put_updates_category(self):
        response = self.client.put(reverse("api:category-detail", args=[self.category.pk]), {
            "name": "Informática", "description": "Livros técnicos"
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.category.refresh_from_db()
        self.assertEqual(self.category.name, "Informática")
        self.assertEqual(self.category.description, "Livros técnicos")

    def test_patch_preserves_omitted_fields(self):
        response = self.client.patch(reverse("api:category-detail", args=[self.category.pk]), {
            "description": "Descrição revisada"
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.category.refresh_from_db()
        self.assertEqual(self.category.name, "Programação")
        self.assertEqual(self.category.description, "Descrição revisada")

    def test_delete_empty_category(self):
        response = self.client.delete(reverse("api:category-detail", args=[self.other_category.pk]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Category.objects.filter(pk=self.other_category.pk).exists())

    def test_delete_category_with_products_returns_validation_error(self):
        response = self.client.delete(reverse("api:category-detail", args=[self.category.pk]))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(Category.objects.filter(pk=self.category.pk).exists())
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())

    def test_missing_blank_and_duplicate_name_do_not_create_records(self):
        initial_count = Category.objects.count()
        for payload in [{}, {"name": " "}, {"name": "Programação"}]:
            with self.subTest(payload=payload):
                response = self.client.post(reverse("api:category-list"), payload, format="json")
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn("name", response.data)
        self.assertEqual(Category.objects.count(), initial_count)

    def test_viewset_list_action_with_request_factory(self):
        request = APIRequestFactory().get("/api/categories/")
        force_authenticate(request, user=self.staff)
        response = CategoryViewSet.as_view({"get": "list"})(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)


class ProductViewSetTests(ViewSetTestBase):
    def test_visitors_can_list_and_retrieve_products_without_login(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(reverse("api:product-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual({item["id"] for item in response.data["results"]}, {
            self.product.pk, self.other_product.pk,
        })
        detail = self.client.get(reverse("api:product-detail", args=[self.product.pk]))
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.data["category"]["id"], self.category.pk)
        self.assertEqual(detail.data["price"], "89.90")

    def test_product_writes_still_require_staff(self):
        detail_url = reverse("api:product-detail", args=[self.product.pk])
        data = {"name": "Alterado", "price": "10.00", "category_id": self.category.pk}
        for user in [None, self.customer]:
            self.client.force_authenticate(user=user)
            for method, url in [
                (self.client.post, reverse("api:product-list")),
                (self.client.put, detail_url),
                (self.client.patch, detail_url),
                (self.client.delete, detail_url),
            ]:
                with self.subTest(user=user, method=method.__name__):
                    response = method(url, data, format="json")
                    self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Product.objects.count(), 2)
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, "Python")
        self.assertEqual(self.product.price, Decimal("89.90"))

    def test_list_and_detail_return_nested_category(self):
        response = self.client.get(reverse("api:product-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)
        detail = self.client.get(reverse("api:product-detail", args=[self.product.pk]))
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.data["category"]["id"], self.category.pk)
        self.assertEqual(detail.data["price"], "89.90")
        self.assertNotIn("category_id", detail.data)

    def test_create_uses_existing_category(self):
        response = self.client.post(reverse("api:product-list"), {
            "name": "APIs REST", "price": "75.50", "category_id": self.category.pk
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        product = Product.objects.get(pk=response.data["id"])
        self.assertEqual(product.category, self.category)
        self.assertEqual(product.price, Decimal("75.50"))
        self.assertEqual(Category.objects.count(), 2)

    def test_put_updates_all_editable_fields(self):
        response = self.client.put(reverse("api:product-detail", args=[self.product.pk]), {
            "name": "Python avançado", "description": "Nova edição", "price": "125.00",
            "active": False, "category_id": self.other_category.pk
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, "Python avançado")
        self.assertEqual(self.product.price, Decimal("125.00"))
        self.assertEqual(self.product.category, self.other_category)
        self.assertFalse(self.product.active)

    def test_patch_changes_price_without_changing_name(self):
        response = self.client.patch(reverse("api:product-detail", args=[self.product.pk]), {
            "price": "79.90"
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, "Python")
        self.assertEqual(self.product.price, Decimal("79.90"))

    def test_delete_product(self):
        response = self.client.delete(reverse("api:product-detail", args=[self.other_product.pk]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Product.objects.filter(pk=self.other_product.pk).exists())

    def test_invalid_price_or_category_does_not_create_product(self):
        count = Product.objects.count()
        for changes in [{"price": "-1.00"}, {"price": "0.00"}, {"category_id": 99999}]:
            with self.subTest(changes=changes):
                response = self.client.post(reverse("api:product-list"), {
                    "name": "Livro", "price": "10.00", "category_id": self.category.pk, **changes
                }, format="json")
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Product.objects.count(), count)

    def test_invalid_patch_keeps_original_price(self):
        response = self.client.patch(reverse("api:product-detail", args=[self.product.pk]), {
            "price": "abc"
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal("89.90"))


class OrderViewSetTests(ViewSetTestBase):
    def test_list_and_detail_return_products_and_categories(self):
        response = self.client.get(reverse("api:order-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        detail = self.client.get(reverse("api:order-detail", args=[self.order.pk]))
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.data["user"], self.customer.pk)
        self.assertEqual(detail.data["products"][0]["category"]["id"], self.category.pk)
        self.assertNotIn("product_ids", detail.data)

    def test_create_order_persists_product_relationships(self):
        response = self.client.post(reverse("api:order-list"), {
            "user": self.customer.pk, "product_ids": [self.product.pk, self.other_product.pk]
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        order = Order.objects.get(pk=response.data["id"])
        self.assertEqual(order.user, self.customer)
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertSetEqual(set(order.products.values_list("pk", flat=True)), {self.product.pk, self.other_product.pk})

    def test_put_replaces_products_and_status(self):
        response = self.client.put(reverse("api:order-detail", args=[self.order.pk]), {
            "user": self.customer.pk, "product_ids": [self.other_product.pk], "status": "completed"
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.COMPLETED)
        self.assertEqual(list(self.order.products.all()), [self.other_product])

    def test_patch_status_preserves_products_and_created_at(self):
        original_date = self.order.created_at
        response = self.client.patch(reverse("api:order-detail", args=[self.order.pk]), {
            "status": "cancelled", "created_at": "2000-01-01T00:00:00Z"
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.CANCELLED)
        self.assertEqual(self.order.created_at, original_date)
        self.assertEqual(list(self.order.products.all()), [self.product])

    def test_delete_order_preserves_product(self):
        response = self.client.delete(reverse("api:order-detail", args=[self.order.pk]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Order.objects.filter(pk=self.order.pk).exists())
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())

    def test_invalid_order_does_not_create_records(self):
        count = Order.objects.count()
        valid = {"user": self.customer.pk, "product_ids": [self.product.pk]}
        for changes in [
            {"product_ids": []}, {"product_ids": [self.product.pk, self.product.pk]},
            {"product_ids": [99999]}, {"user": 99999}, {"status": "invalido"},
        ]:
            with self.subTest(changes=changes):
                response = self.client.post(reverse("api:order-list"), {**valid, **changes}, format="json")
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Order.objects.count(), count)


class RoutingAndPermissionTests(ViewSetTestBase):
    def test_api_root_contains_registered_routes(self):
        response = self.client.get(reverse("api:api-root"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(set(response.data), {"categories", "products", "orders"})

    def test_home_redirects_to_api(self):
        self.assertRedirects(self.client.get("/"), reverse("api:api-root"))

    def test_unknown_ids_return_404(self):
        for resource in ["category", "product", "order"]:
            with self.subTest(resource=resource):
                response = self.client.get(reverse(f"api:{resource}-detail", args=[99999]))
                self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_visitors_can_read_products_but_cannot_write_management_endpoints(self):
        self.client.force_authenticate(user=None)
        for resource in ["category", "product", "order"]:
            with self.subTest(resource=resource):
                url = reverse(f"api:{resource}-list")
                expected = status.HTTP_401_UNAUTHORIZED if resource == "order" else status.HTTP_403_FORBIDDEN
                read_expected = status.HTTP_200_OK if resource == "product" else expected
                self.assertEqual(self.client.get(url).status_code, read_expected)
                self.assertEqual(self.client.post(url, {}, format="json").status_code, expected)

    def test_regular_user_can_read_products_but_not_private_resources(self):
        self.client.force_authenticate(user=self.customer)
        for resource in ["category", "product", "order"]:
            with self.subTest(resource=resource):
                response = self.client.get(reverse(f"api:{resource}-list"))
                expected = status.HTTP_200_OK if resource == "product" else status.HTTP_403_FORBIDDEN
                self.assertEqual(response.status_code, expected)

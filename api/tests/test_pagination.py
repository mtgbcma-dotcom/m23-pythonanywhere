from io import StringIO
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from ..models import Category, Order, Product


class PaginationTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_user(username="gestor", is_staff=True)
        for number in range(12):
            category = Category.objects.create(name=f"Categoria {number:02d}")
            product = Product.objects.create(name=f"Livro {number:02d}", price="10.00", category=category)
            order = Order.objects.create(user=cls.staff)
            order.products.add(product)

    def setUp(self):
        self.client.force_authenticate(user=self.staff)

    def test_visitors_can_paginate_products_while_orders_require_token(self):
        self.client.force_authenticate(user=None)
        first = self.client.get(reverse("api:product-list"))
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(first.data["count"], 12)
        self.assertEqual(len(first.data["results"]), 5)
        self.assertIsNone(first.data["previous"])
        second = self.client.get(first.data["next"])
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(len(second.data["results"]), 5)
        self.assertTrue(second.data["previous"])
        self.assertTrue(second.data["next"])
        self.assertTrue(
            {item["id"] for item in first.data["results"]}.isdisjoint(
                item["id"] for item in second.data["results"]
            )
        )
        self.assertEqual(
            self.client.get(reverse("api:order-list")).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_first_page_has_metadata_and_five_results_on_all_lists(self):
        for resource in ["category", "product", "order"]:
            with self.subTest(resource=resource):
                response = self.client.get(reverse(f"api:{resource}-list"))
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(set(response.data), {"count", "next", "previous", "results"})
                self.assertEqual(response.data["count"], 12)
                self.assertEqual(len(response.data["results"]), 5)
                self.assertIsNone(response.data["previous"])
                self.assertEqual(parse_qs(urlsplit(response.data["next"]).query), {"page": ["2"]})

    def test_second_page_has_previous_and_next(self):
        for resource in ["category", "product", "order"]:
            with self.subTest(resource=resource):
                response = self.client.get(reverse(f"api:{resource}-list"), {"page": 2})
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.data["count"], 12)
                self.assertEqual(len(response.data["results"]), 5)
                self.assertIsNotNone(response.data["previous"])
                self.assertEqual(parse_qs(urlsplit(response.data["next"]).query), {"page": ["3"]})

    def test_last_page_has_only_remaining_results(self):
        for resource in ["category", "product", "order"]:
            with self.subTest(resource=resource):
                response = self.client.get(reverse(f"api:{resource}-list"), {"page": 3})
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(len(response.data["results"]), 2)
                self.assertIsNone(response.data["next"])
                self.assertEqual(parse_qs(urlsplit(response.data["previous"]).query), {"page": ["2"]})

    def test_following_links_retrieves_every_record_once(self):
        for resource, model in [("category", Category), ("product", Product), ("order", Order)]:
            with self.subTest(resource=resource):
                url = reverse(f"api:{resource}-list")
                collected = []
                pages = 0
                while url:
                    parts = urlsplit(url)
                    response = self.client.get(parts.path + ("?" + parts.query if parts.query else ""))
                    self.assertEqual(response.status_code, status.HTTP_200_OK)
                    collected.extend(item["id"] for item in response.data["results"])
                    url = response.data["next"]
                    pages += 1
                    self.assertLessEqual(pages, 3)
                self.assertEqual(pages, 3)
                self.assertEqual(collected, list(model.objects.order_by("id").values_list("id", flat=True)))
                self.assertEqual(len(collected), len(set(collected)))

    def test_invalid_or_out_of_range_page_returns_404(self):
        for resource in ["category", "product", "order"]:
            for page in [0, -1, 4, "abc", "1.5"]:
                with self.subTest(resource=resource, page=page):
                    response = self.client.get(reverse(f"api:{resource}-list"), {"page": page})
                    self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_last_keyword_points_to_last_page(self):
        response = self.client.get(reverse("api:product-list"), {"page": "last"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertIsNone(response.data["next"])

    def test_product_detail_is_not_wrapped_in_pagination(self):
        product = Product.objects.first()
        response = self.client.get(reverse("api:product-detail", args=[product.pk]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], product.pk)
        self.assertNotIn("results", response.data)

    def test_nested_product_category_is_preserved_in_paginated_results(self):
        response = self.client.get(reverse("api:product-list"), {"page": 2})
        for item in response.data["results"]:
            self.assertEqual(item["category"]["id"], Product.objects.get(pk=item["id"]).category_id)

    def test_orders_keep_nested_products_and_categories(self):
        response = self.client.get(reverse("api:order-list"), {"page": 2})
        for item in response.data["results"]:
            self.assertEqual(len(item["products"]), 1)
            self.assertIn("category", item["products"][0])

    def test_page_links_preserve_other_query_parameters(self):
        response = self.client.get(reverse("api:product-list"), {"page": 2, "format": "json"})
        for key in ["next", "previous"]:
            self.assertEqual(parse_qs(urlsplit(response.data[key]).query)["format"], ["json"])


class EmptyPaginationTests(APITestCase):
    def setUp(self):
        staff = get_user_model().objects.create_user(username="gestor", is_staff=True)
        self.client.force_authenticate(user=staff)

    def test_empty_lists_have_valid_pagination_metadata(self):
        for resource in ["category", "product", "order"]:
            with self.subTest(resource=resource):
                response = self.client.get(reverse(f"api:{resource}-list"))
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.data, {"count": 0, "next": None, "previous": None, "results": []})


class DemoCommandTests(TestCase):
    def test_demo_command_can_be_repeated_without_duplicates(self):
        call_command("seed_demo", stdout=StringIO())
        call_command("seed_demo", stdout=StringIO())
        self.assertEqual(Category.objects.count(), 12)
        self.assertEqual(Product.objects.count(), 12)

    def test_invalid_quantity_does_not_create_demo_records(self):
        with self.assertRaises(CommandError):
            call_command("seed_demo", quantity=0, stdout=StringIO())
        self.assertEqual(Category.objects.count(), 0)
        self.assertEqual(Product.objects.count(), 0)

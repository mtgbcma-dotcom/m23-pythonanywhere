from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from ..models import Category, Order, Product
from ..serializers import CategorySerializer, OrderSerializer, ProductSerializer


class CategorySerializerTests(TestCase):
    def test_valid_data_creates_category(self):
        serializer = CategorySerializer(data={"name": "Programação"})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        category = serializer.save()
        category.refresh_from_db()
        self.assertEqual(category.name, "Programação")
        self.assertEqual(category.description, "")

    def test_name_is_required(self):
        serializer = CategorySerializer(data={"description": "Livros técnicos"})
        self.assertFalse(serializer.is_valid())
        self.assertIn("name", serializer.errors)

    def test_invalid_name_is_rejected(self):
        for name in ["", "   ", "a" * 101]:
            with self.subTest(name=name):
                serializer = CategorySerializer(data={"name": name})
                self.assertFalse(serializer.is_valid())
                self.assertIn("name", serializer.errors)

    def test_duplicate_name_is_rejected(self):
        Category.objects.create(name="Automação")
        serializer = CategorySerializer(data={"name": "Automação"})
        self.assertFalse(serializer.is_valid())
        self.assertIn("name", serializer.errors)

    def test_representation_has_expected_fields(self):
        category = Category.objects.create(name="Elétrica", description="Circuitos")
        self.assertEqual(CategorySerializer(category).data, {
            "id": category.pk, "name": "Elétrica", "description": "Circuitos"
        })

    def test_update_preserves_read_only_id(self):
        category = Category.objects.create(name="Técnicos")
        original_id = category.pk
        serializer = CategorySerializer(
            category, data={"id": 99999, "description": "Manuais"}, partial=True
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        category.refresh_from_db()
        self.assertEqual(category.pk, original_id)
        self.assertEqual(category.description, "Manuais")
        self.assertEqual(category.name, "Técnicos")


class ProductSerializerTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Programação")
        self.data = {
            "name": "Python na prática",
            "description": "Exercícios de programação",
            "price": "89.90",
            "category_id": self.category.pk,
        }

    def test_valid_data_creates_product_with_category(self):
        serializer = ProductSerializer(data=self.data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        product = serializer.save()
        product.refresh_from_db()
        self.assertEqual(product.name, self.data["name"])
        self.assertEqual(product.description, self.data["description"])
        self.assertEqual(product.price, Decimal("89.90"))
        self.assertEqual(product.category, self.category)
        self.assertTrue(product.active)

    def test_required_fields(self):
        for field in ["name", "price", "category_id"]:
            with self.subTest(field=field):
                data = self.data.copy()
                del data[field]
                serializer = ProductSerializer(data=data)
                self.assertFalse(serializer.is_valid())
                self.assertIn(field, serializer.errors)

    def test_invalid_name(self):
        for name in ["", "   ", "a" * 151]:
            with self.subTest(name=name):
                serializer = ProductSerializer(data={**self.data, "name": name})
                self.assertFalse(serializer.is_valid())
                self.assertIn("name", serializer.errors)

    def test_invalid_prices(self):
        for price in ["0.00", "-1.00", "abc", "1.234", "100000000.00"]:
            with self.subTest(price=price):
                serializer = ProductSerializer(data={**self.data, "price": price})
                self.assertFalse(serializer.is_valid())
                self.assertIn("price", serializer.errors)

    def test_nonexistent_category(self):
        serializer = ProductSerializer(data={**self.data, "category_id": 99999})
        self.assertFalse(serializer.is_valid())
        self.assertIn("category_id", serializer.errors)

    def test_invalid_boolean(self):
        serializer = ProductSerializer(data={**self.data, "active": "talvez"})
        self.assertFalse(serializer.is_valid())
        self.assertIn("active", serializer.errors)

    def test_representation_includes_nested_category(self):
        product = Product.objects.create(
            name="Python na prática", price=Decimal("89.90"), category=self.category
        )
        data = ProductSerializer(product).data
        self.assertEqual(set(data), {
            "id", "name", "description", "price", "active", "category"
        })
        self.assertEqual(data["id"], product.pk)
        self.assertEqual(data["price"], "89.90")
        self.assertEqual(data["category"], {
            "id": self.category.pk, "name": "Programação", "description": ""
        })
        self.assertNotIn("category_id", data)

    def test_partial_update_changes_category_and_price(self):
        product = Product.objects.create(
            name="Python", price="89.90", category=self.category
        )
        other = Category.objects.create(name="Engenharia")
        serializer = ProductSerializer(
            product, data={"price": "95.00", "category_id": other.pk}, partial=True
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        product.refresh_from_db()
        self.assertEqual(product.category, other)
        self.assertEqual(product.price, Decimal("95.00"))
        self.assertEqual(product.name, "Python")

    def test_optional_description_and_false_active(self):
        data = {key: value for key, value in self.data.items() if key != "description"}
        serializer = ProductSerializer(data={**data, "active": False})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        product = serializer.save()
        product.refresh_from_db()
        self.assertEqual(product.description, "")
        self.assertFalse(product.active)


class OrderSerializerTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="leitor")
        self.category = Category.objects.create(name="Técnicos")
        self.product = Product.objects.create(
            name="Comandos elétricos", price="75.00", category=self.category
        )
        self.other = Product.objects.create(
            name="Automação industrial", price="110.00", category=self.category
        )
        self.data = {
            "user": self.user.pk,
            "product_ids": [self.product.pk, self.other.pk],
        }

    def test_valid_data_creates_order_and_relationships(self):
        serializer = OrderSerializer(data=self.data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        order = serializer.save()
        order.refresh_from_db()
        self.assertEqual(order.user, self.user)
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertIsNotNone(order.created_at)
        self.assertSetEqual(
            set(order.products.values_list("pk", flat=True)),
            {self.product.pk, self.other.pk},
        )

    def test_required_fields(self):
        for field in ["user", "product_ids"]:
            with self.subTest(field=field):
                data = self.data.copy()
                del data[field]
                serializer = OrderSerializer(data=data)
                self.assertFalse(serializer.is_valid())
                self.assertIn(field, serializer.errors)

    def test_nonexistent_user(self):
        serializer = OrderSerializer(data={**self.data, "user": 99999})
        self.assertFalse(serializer.is_valid())
        self.assertIn("user", serializer.errors)

    def test_nonexistent_product(self):
        serializer = OrderSerializer(data={**self.data, "product_ids": [99999]})
        self.assertFalse(serializer.is_valid())
        self.assertIn("product_ids", serializer.errors)

    def test_empty_products(self):
        serializer = OrderSerializer(data={**self.data, "product_ids": []})
        self.assertFalse(serializer.is_valid())
        self.assertIn("product_ids", serializer.errors)

    def test_duplicate_products(self):
        serializer = OrderSerializer(data={
            **self.data, "product_ids": [self.product.pk, self.product.pk]
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn("product_ids", serializer.errors)

    def test_invalid_status(self):
        serializer = OrderSerializer(data={**self.data, "status": "desconhecido"})
        self.assertFalse(serializer.is_valid())
        self.assertIn("status", serializer.errors)

    def test_representation_includes_products_and_categories(self):
        order = Order.objects.create(user=self.user)
        order.products.set([self.product, self.other])
        data = OrderSerializer(order).data
        self.assertEqual(set(data), {"id", "user", "products", "status", "created_at"})
        self.assertEqual(data["id"], order.pk)
        self.assertEqual(data["user"], self.user.pk)
        self.assertEqual(data["status"], "pending")
        self.assertIsNotNone(data["created_at"])
        self.assertEqual({item["id"] for item in data["products"]}, {
            self.product.pk, self.other.pk
        })
        for item in data["products"]:
            self.assertEqual(item["category"]["id"], self.category.pk)
            self.assertEqual(item["category"]["name"], "Técnicos")
        self.assertNotIn("product_ids", data)

    def test_update_replaces_product_relationships(self):
        order = Order.objects.create(user=self.user)
        order.products.set([self.product, self.other])
        serializer = OrderSerializer(
            order,
            data={"product_ids": [self.other.pk], "status": "completed"},
            partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.COMPLETED)
        self.assertEqual(list(order.products.all()), [self.other])

    def test_partial_update_preserves_products_and_read_only_fields(self):
        order = Order.objects.create(user=self.user)
        order.products.add(self.product)
        original_id = order.pk
        original_date = order.created_at
        serializer = OrderSerializer(
            order,
            data={"status": "cancelled", "id": 99999, "created_at": "2000-01-01"},
            partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        order.refresh_from_db()
        self.assertEqual(order.pk, original_id)
        self.assertEqual(order.created_at, original_date)
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(list(order.products.all()), [self.product])

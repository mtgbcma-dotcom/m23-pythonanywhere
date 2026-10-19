from rest_framework import serializers

from .models import Category, Order, Product


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "description"]
        read_only_fields = ["id"]


class ProductSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), source="category", write_only=True
    )

    class Meta:
        model = Product
        fields = [
            "id", "name", "description", "price", "active", "category", "category_id"
        ]
        read_only_fields = ["id"]


class OrderSerializer(serializers.ModelSerializer):
    products = ProductSerializer(many=True, read_only=True)
    product_ids = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        source="products",
        many=True,
        write_only=True,
        allow_empty=False,
    )

    class Meta:
        model = Order
        fields = ["id", "user", "products", "product_ids", "status", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_product_ids(self, products):
        ids = [product.pk for product in products]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError("Não repita produtos no mesmo pedido.")
        return products

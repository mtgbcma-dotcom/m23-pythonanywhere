from django.db.models.deletion import ProtectedError
from rest_framework import serializers, viewsets
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAdminUser

from .models import Category, Order, Product
from .serializers import CategorySerializer, OrderSerializer, ProductSerializer


class CategoryViewSet(viewsets.ModelViewSet):
    """Cadastro de categorias da livraria."""

    queryset = Category.objects.all().order_by("id")
    serializer_class = CategorySerializer
    permission_classes = [IsAdminUser]

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError:
            raise serializers.ValidationError({
                "detail": "Não é possível excluir uma categoria com produtos vinculados."
            })


class ProductViewSet(viewsets.ModelViewSet):
    """Cadastro de produtos com a categoria na representação de leitura."""

    queryset = Product.objects.select_related("category").order_by("id")
    serializer_class = ProductSerializer
    permission_classes = [IsAdminUser]


class OrderViewSet(viewsets.ModelViewSet):
    """Cadastro de pedidos e seus produtos, autenticado somente por token."""

    authentication_classes = [TokenAuthentication]

    queryset = Order.objects.select_related("user").prefetch_related(
        "products__category"
    ).order_by("id")
    serializer_class = OrderSerializer
    permission_classes = [IsAdminUser]

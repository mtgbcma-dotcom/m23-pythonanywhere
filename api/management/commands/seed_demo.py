from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from api.models import Category, Product


class Command(BaseCommand):
    help = "Cria categorias e produtos de exemplo para testar a paginação."

    def add_arguments(self, parser):
        parser.add_argument("--quantity", type=int, default=12)

    @transaction.atomic
    def handle(self, *args, **options):
        quantity = options["quantity"]
        if not 1 <= quantity <= 100:
            raise CommandError("A quantidade deve estar entre 1 e 100.")
        categories_created = products_created = 0
        for number in range(1, quantity + 1):
            category, created = Category.objects.get_or_create(
                name=f"Categoria de exemplo {number:02d}",
                defaults={"description": "Dados para demonstração da paginação."},
            )
            categories_created += int(created)
            _, created = Product.objects.get_or_create(
                name=f"Livro de exemplo {number:02d}", category=category,
                defaults={"price": Decimal("10.00") + number, "active": True},
            )
            products_created += int(created)
        self.stdout.write(self.style.SUCCESS(
            f"Criadas {categories_created} categorias e {products_created} produtos de exemplo."
        ))

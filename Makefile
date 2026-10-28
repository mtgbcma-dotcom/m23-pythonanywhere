.PHONY: up down logs check test migrate superuser seed network

up:
	docker compose up -d --build --wait

down:
	docker compose down

logs:
	docker compose logs -f web

check:
	docker compose exec web poetry run python manage.py check

test:
	docker compose exec web poetry run python manage.py test --verbosity 2

migrate:
	docker compose exec web poetry run python manage.py migrate

superuser:
	docker compose exec web poetry run python manage.py createsuperuser

seed:
	docker compose exec web poetry run python manage.py seed_demo

network:
	docker network inspect m23-pythonanywhere_bookstore_network

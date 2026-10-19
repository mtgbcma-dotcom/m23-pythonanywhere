# syntax=docker/dockerfile:1
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements*.txt .
RUN python -m pip install --no-cache-dir -r requirements-postgresql.txt

COPY . .

RUN python manage.py collectstatic --noinput \
    && adduser --disabled-password --gecos "" app \
    && mkdir -p /data \
    && chown app:app /data

USER app

EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate --noinput && exec python manage.py runserver 0.0.0.0:8000 --noreload"]

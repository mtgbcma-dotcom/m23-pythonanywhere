from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
from rest_framework.authtoken.views import obtain_auth_token

from . import views

urlpatterns = [
    path("hello/", views.hello, name="hello"),
    path("update_server/", views.update_server, name="update_server"),
    path("", RedirectView.as_view(pattern_name="api:api-root", permanent=False)),
    path("admin/", admin.site.urls),
    path("api/token/", obtain_auth_token, name="api-token-auth"),
    path("api/", include(("api.urls", "api"), namespace="api")),
    path("api-auth/", include("rest_framework.urls")),
]

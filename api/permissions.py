from rest_framework.permissions import SAFE_METHODS, IsAdminUser


class IsAdminUserOrReadOnly(IsAdminUser):
    """Consulta pública; alterações restritas aos administradores."""

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or super().has_permission(request, view)

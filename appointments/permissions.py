from rest_framework.permissions import BasePermission, SAFE_METHODS
from appointments.models import CustomUser  # ajusta el import


class EsAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_staff


class EsDoctor(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        try:
            # Obtiene el CustomUser real basado en el Auth0 ID
            auth0_id = request.user.payload.get("sub")
            custom_user = CustomUser.objects.get(auth0_id=auth0_id)
            # Verifica el rol en tu modelo
            return custom_user.role == "doctor"
        except (CustomUser.DoesNotExist, AttributeError):
            # Si el usuario no existe en la DB o no tiene el payload, deniega el acceso
            return False

    def has_object_permission(self, request, view, obj):
        return obj.doctor.email == request.user.email


class EsPaciente(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated  # ignora role por ahora

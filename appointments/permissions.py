# src/appointments/permissions.py
from rest_framework.permissions import BasePermission
from .models import CustomUser, Doctor, Paciente  # Asegúrate de importar tus modelos


class EsAdmin(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Intenta obtener el auth0_id de varias maneras, porque el objeto request.user
        # puede variar ligeramente dependiendo de cómo el middleware lo envuelve.
        auth0_id = getattr(
            request.user, "auth0_id", None
        )  # Si el middleware lo añade directamente
        if not auth0_id and hasattr(request.user, "payload"):
            auth0_id = request.user.payload.get("sub")

        if not auth0_id:
            return False

        try:
            custom_user = CustomUser.objects.get(auth0_id=auth0_id)
            return custom_user.is_staff
        except CustomUser.DoesNotExist:
            return False


class EsDoctor(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Intenta obtener el auth0_id de varias maneras para mayor robustez
        auth0_id = getattr(
            request.user, "auth0_id", None
        )  # Si el middleware lo añade directamente
        if not auth0_id and hasattr(request.user, "payload"):
            auth0_id = request.user.payload.get("sub")

        if not auth0_id:
            return False

        try:
            custom_user = CustomUser.objects.get(auth0_id=auth0_id)
            # Verifica que el CustomUser tiene un perfil de doctor
            return (
                hasattr(custom_user, "doctor_profile")
                and custom_user.doctor_profile is not None
            )
        except CustomUser.DoesNotExist:
            return False


class EsPaciente(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Intenta obtener el auth0_id de varias maneras
        auth0_id = getattr(
            request.user, "auth0_id", None
        )  # Si el middleware lo añade directamente
        if not auth0_id and hasattr(request.user, "payload"):
            auth0_id = request.user.payload.get("sub")

        if not auth0_id:
            return False

        try:
            custom_user = CustomUser.objects.get(auth0_id=auth0_id)
            # Verifica que el CustomUser tiene un perfil de paciente
            return (
                hasattr(custom_user, "paciente_profile")
                and custom_user.paciente_profile is not None
            )
        except CustomUser.DoesNotExist:
            return False

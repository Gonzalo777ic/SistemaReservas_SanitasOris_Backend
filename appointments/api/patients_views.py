# Django Imports
from django.shortcuts import get_object_or_404

# DRF Imports
from rest_framework import viewsets, filters, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

# Project-specific Imports
from ..models import Paciente, CustomUser
from ..serializers import PacienteSerializer
from ..permissions import EsAdmin


class PacienteViewSet(viewsets.ModelViewSet):
    serializer_class = PacienteSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["user__first_name", "user__last_name", "user__email"]

    def get_permissions(self):
        user = getattr(self.request, "user", None)
        if user and getattr(user, "is_staff", False):
            return [EsAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user

        if not user.is_authenticated:
            return Paciente.objects.none()

        if getattr(user, "is_staff", False):
            # Solo los administradores pueden ver todos los pacientes
            # Filtramos para asegurar que solo los pacientes con un usuario válido sean devueltos
            queryset = Paciente.objects.filter(user__isnull=False)
            print(
                f"DEBUG: PacienteViewSet get_queryset encontró {queryset.count()} pacientes."
            )
            return queryset

        # Los pacientes solo pueden ver su propio perfil
        # Primero, obtenemos el CustomUser de Django a partir del Auth0User
        auth0_id = getattr(user, "username", None) or getattr(user, "payload", {}).get(
            "sub"
        )
        if not auth0_id:
            return Paciente.objects.none()

        try:
            custom_user = CustomUser.objects.get(auth0_id=auth0_id)
            return Paciente.objects.filter(user=custom_user)
        except CustomUser.DoesNotExist:
            return Paciente.objects.none()


@api_view(["GET"])
def get_paciente_by_email(request, email):
    paciente = get_object_or_404(Paciente, user__email=email)
    serializer = PacienteSerializer(paciente)
    return Response(serializer.data, status=status.HTTP_200_OK)

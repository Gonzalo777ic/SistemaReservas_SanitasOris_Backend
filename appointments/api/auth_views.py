# DRF Imports
from rest_framework import viewsets, mixins, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

# Django Imports
from django.shortcuts import get_object_or_404
from django.db import transaction

# Project-specific Imports
from ..models import CustomUser, Paciente, Doctor
from ..serializers import (
    CustomUserSerializer,
    PacienteUpdateSerializer,
    DoctorUpdateSerializer,
)


class CustomUserViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = CustomUser.objects.all()
    serializer_class = CustomUserSerializer

    # ⚠️ En tu endpoint real, deberías añadir permisos para restringir el acceso
    # permission_classes = [IsAuthenticated, IsAdminUser]

    @action(detail=True, methods=["patch"], url_path="promote_to_doctor")
    def promote_to_doctor(self, request, pk=None):
        try:
            user = self.get_object()
            if user.role != "paciente":
                return Response(
                    {"error": "Solo se puede promover a un paciente a doctor."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            user.role = "doctor"
            user.is_staff = True
            user.save()
            return Response(
                {"status": f"Usuario {user.email} promovido a doctor."},
                status=status.HTTP_200_OK,
            )
        except CustomUser.DoesNotExist:
            return Response(
                {"error": "Usuario no encontrado."}, status=status.HTTP_404_NOT_FOUND
            )

    # 🚨 Nueva acción para degradar a un doctor a paciente
    @action(detail=True, methods=["patch"], url_path="revert_to_paciente")
    def revert_to_paciente(self, request, pk=None):
        try:
            user = self.get_object()
            if user.role != "doctor":
                return Response(
                    {"error": "Solo se puede degradar a un doctor a paciente."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            user.role = "paciente"
            user.is_staff = False
            user.save()
            return Response(
                {"status": f"Usuario {user.email} degradado a paciente."},
                status=status.HTTP_200_OK,
            )
        except CustomUser.DoesNotExist:
            return Response(
                {"error": "Usuario no encontrado."}, status=status.HTTP_404_NOT_FOUND
            )


@api_view(["POST"])
@permission_classes([IsAuthenticated])  # protegido con JWT de Auth0
def sync_user(request):
    """
    Crea o actualiza un CustomUser y su perfil de Paciente asociado a partir de Auth0.
    """
    data = request.data
    email = data.get("email")
    nombre_completo = data.get("name", "")
    auth0_id = data.get("sub")  # 👈 viene en el token de Auth0 normalmente
    print("SYNC USER request.data:", data)

    if not email or not auth0_id:
        return Response({"error": "Email y Auth0 ID son requeridos"}, status=400)

    # separar nombre/apellido básico
    nombre_split = nombre_completo.split(" ", 1)
    nombre = nombre_split[0]
    apellido = nombre_split[1] if len(nombre_split) > 1 else ""

    # 1️⃣ Crear/obtener CustomUser
    user, created = CustomUser.objects.get_or_create(
        auth0_id=auth0_id,
        defaults={
            "email": email,
            "first_name": nombre,
            "last_name": apellido,
            "role": "paciente",  # por defecto todos entran como pacientes
            "is_staff": False,
            "is_superuser": False,
        },
    )

    # si ya existía pero cambió algo en Auth0 → actualizar
    if not created:
        updated = False
        if user.email != email:
            user.email = email
            updated = True
        if user.first_name != nombre:
            user.first_name = nombre
            updated = True
        if user.last_name != apellido:
            user.last_name = apellido
            updated = True
        if updated:
            user.save()

    # 2️⃣ Crear/obtener Paciente vinculado
    paciente, pac_created = Paciente.objects.get_or_create(user=user)

    return Response(
        {
            "msg": "Usuario sincronizado",
            "user_id": user.id,
            "paciente_id": paciente.id,
            "created_user": created,
            "created_paciente": pac_created,
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def whoami(request):
    auth0_user = request.user
    print("🔹 whoami: request.user =", auth0_user)

    # Extraer sub desde Auth0User
    auth0_id = None
    if hasattr(auth0_user, "payload"):  # caso Auth0User wrapper
        auth0_id = auth0_user.payload.get("sub")
    else:
        auth0_id = getattr(auth0_user, "sub", None)

    print("🔹 whoami: auth0_id extraído =", auth0_id)

    if not auth0_id:
        return Response({"detail": "No se pudo extraer auth0_id"}, status=400)

    try:
        user = CustomUser.objects.get(auth0_id=auth0_id)
        print("🔹 whoami: CustomUser encontrado =", user, "| staff =", user.is_staff)
    except CustomUser.DoesNotExist:
        print("⚠️ whoami: CustomUser no encontrado")
        return Response({"detail": "Usuario no encontrado"}, status=404)

    # Determinar rol
    role = "paciente"
    if getattr(user, "is_staff", False):
        role = "admin"
    elif hasattr(user, "doctor_profile"):
        role = "doctor"
    elif hasattr(user, "paciente_profile"):
        role = "paciente"

    print(f"✅ Rol asignado para {user.email}: {role}")

    return Response(
        {
            "email": user.email,
            "role": role,
            "nombre": f"{user.first_name} {user.last_name}".strip() or user.email,
        }
    )


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def update_profile(request):
    auth0_id = request.user.payload.get("sub")

    try:
        user = CustomUser.objects.get(auth0_id=auth0_id)
    except CustomUser.DoesNotExist:
        return Response(
            {"error": "Usuario no encontrado en la base de datos."},
            status=status.HTTP_404_NOT_FOUND,
        )

    # 🛑 1. CRITICAL CORRECTION: PREVENT ROLE CHANGE
    # Explicitly check if 'role' is in the request data and return an error if it is.
    if "role" in request.data:
        return Response(
            {"error": "No se puede cambiar el rol del usuario."},
            status=status.HTTP_403_FORBIDDEN,
        )

    # 🛑 2. CORRECTED LOGIC: Admins can't update their own profiles this way.
    if user.role == "admin":
        return Response(
            {
                "message": "El perfil de administrador no es editable a través de esta API."
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    # The rest of the logic remains the same
    if user.role == "paciente":
        try:
            profile = Paciente.objects.get(user=user)
            serializer = PacienteUpdateSerializer(
                profile, data=request.data, partial=True
            )
        except Paciente.DoesNotExist:
            return Response(
                {"error": "Perfil de paciente no encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )

    elif user.role == "doctor":
        try:
            profile = Doctor.objects.get(user=user)
            serializer = DoctorUpdateSerializer(
                profile, data=request.data, partial=True
            )
        except Doctor.DoesNotExist:
            return Response(
                {"error": "Perfil de doctor no encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )

    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

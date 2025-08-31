# appointments/views.py
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404

from rest_framework import viewsets, filters, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from django_filters.rest_framework import DjangoFilterBackend

from .models import Paciente, Doctor, Reserva
from .serializers import PacienteSerializer, DoctorSerializer, ReservaSerializer
from .permissions import EsAdmin, EsDoctor, EsPaciente


# -----------------------------
# Pacientes
# -----------------------------
class PacienteViewSet(viewsets.ModelViewSet):
    queryset = Paciente.objects.all()
    serializer_class = PacienteSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["nombre", "apellido", "email"]

    def get_permissions(self):
        """
        - Admin puede ver/editar todos los pacientes.
        - Otros usuarios autenticados solo pueden ver su perfil.
        """
        user = getattr(self.request, "user", None)
        if user and getattr(user, "is_staff", False):
            return [EsAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user

        if not user.is_authenticated:
            return Reserva.objects.none()

        # 🟢 Solución: Usar getattr para acceder a is_staff de forma segura
        if getattr(user, "is_staff", False):
            return Reserva.objects.all()

        # ⚠️ Si `hasattr` da problemas con Auth0, es mejor usar `try/except` o
        # simplemente verificar el rol del usuario de otra manera.
        # Por ejemplo, puedes verificar si el usuario tiene un perfil de doctor.
        try:
            if hasattr(user, "doctor_profile"):
                return Reserva.objects.filter(doctor__email=user.email)
        except AttributeError:
            pass  # Ignora si el atributo no existe

        return Reserva.objects.filter(paciente__email=user.email)


@api_view(["POST"])
@permission_classes([IsAuthenticated])  # 👈 protegido con JWT de Auth0
def sync_user(request):
    """
    Crea o actualiza un usuario y su paciente asociado a partir de Auth0.
    """
    data = request.data
    email = data.get("email")
    nombre_completo = data.get("name", "")

    if not email:
        return Response({"error": "Email es requerido"}, status=400)

    # separar nombre/apellido básico
    nombre_split = nombre_completo.split(" ", 1)
    nombre = nombre_split[0]
    apellido = nombre_split[1] if len(nombre_split) > 1 else ""

    # 1️⃣ Crear/obtener User
    user, created = User.objects.get_or_create(
        username=email,
        defaults={
            "email": email,
            "first_name": nombre,
            "last_name": apellido,
            "is_staff": False,
            "is_superuser": False,
        },
    )

    # garantizar que no sea staff por accidente
    if user.is_staff:
        user.is_staff = False
        user.save()

    # 2️⃣ Crear/obtener Paciente
    paciente, pac_created = Paciente.objects.get_or_create(
        user=user,
        defaults={"nombre": nombre, "apellido": apellido, "email": email},
    )

    return Response(
        {
            "msg": "Usuario sincronizado",
            "user_id": user.id,
            "paciente_id": paciente.id,
            "created": created or pac_created,
        }
    )


@api_view(["GET"])
def get_paciente_by_email(request, email):
    paciente = get_object_or_404(Paciente, email=email)
    serializer = PacienteSerializer(paciente)
    return Response(serializer.data, status=status.HTTP_200_OK)


# -----------------------------
# Doctores
# -----------------------------
class DoctorViewSet(viewsets.ModelViewSet):
    queryset = Doctor.objects.all()
    serializer_class = DoctorSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["nombre", "apellido", "especialidad", "email"]

    def get_permissions(self):
        """
        - GET público (los pacientes necesitan ver doctores).
        - POST/PUT/DELETE solo admin.
        """
        if self.action in ["list", "retrieve"]:
            return [AllowAny()]
        return [EsAdmin()]


# -----------------------------
# Reservas
# -----------------------------
class ReservaViewSet(viewsets.ModelViewSet):
    queryset = Reserva.objects.all()
    serializer_class = ReservaSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["paciente__id", "doctor__id", "estado"]
    search_fields = ["paciente__nombre", "doctor__nombre"]

    def get_permissions(self):
        user = self.request.user

        if self.action == "create":
            return [EsPaciente()]

        if self.action in ["update", "partial_update", "destroy"]:
            if getattr(user, "is_staff", False):
                return [EsAdmin()]
            elif hasattr(user, "doctor_profile"):
                return [EsDoctor()]
            return [EsPaciente()]

        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user

        if not user.is_authenticated:
            return Reserva.objects.none()

        # 🟢 CORRECCIÓN: Usar getattr para la verificación de staff
        if getattr(user, "is_staff", False):
            return Reserva.objects.all()

        # El resto de la lógica para doctor y paciente
        if hasattr(user, "doctor_profile"):
            return Reserva.objects.filter(doctor__email=user.email)

        return Reserva.objects.filter(paciente__email=user.email)

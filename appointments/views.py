# appointments/views.py
from django.shortcuts import get_object_or_404

from rest_framework import viewsets, filters, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from django_filters.rest_framework import DjangoFilterBackend

from .models import Paciente, Doctor, Reserva, CustomUser
from .serializers import PacienteSerializer, DoctorSerializer, ReservaSerializer
from .permissions import EsAdmin, EsDoctor, EsPaciente

from django.utils.timezone import now
from django.db.models import Count
from datetime import timedelta


# -----------------------------
# Pacientes
# -----------------------------
class PacienteViewSet(viewsets.ModelViewSet):
    queryset = Paciente.objects.all()
    serializer_class = PacienteSerializer
    filter_backends = [filters.SearchFilter]
    # ⚠️ Recuerda: ya no existen campos nombre/apellido/email directos en Paciente
    # Son parte de user, así que ajusta los search_fields
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
            return Paciente.objects.all()

        return Paciente.objects.filter(user=user)


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
def get_paciente_by_email(request, email):
    paciente = get_object_or_404(Paciente, user__email=email)
    serializer = PacienteSerializer(paciente)
    return Response(serializer.data, status=status.HTTP_200_OK)


# -----------------------------
# Doctores
# -----------------------------
class DoctorViewSet(viewsets.ModelViewSet):
    queryset = Doctor.objects.all()
    serializer_class = DoctorSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = [
        "user__first_name",
        "user__last_name",
        "user__email",
        "especialidad",
    ]

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
        auth0_user = self.request.user
        print("🔹 Auth0User:", auth0_user)

        # 🔹 Extraer auth0_id correctamente
        auth0_id = getattr(auth0_user, "username", None) or getattr(
            auth0_user, "payload", {}
        ).get("sub")
        print("🔹 auth0_id extraído:", auth0_id)

        if not auth0_id:
            print("⚠️ No se pudo extraer auth0_id")
            return Reserva.objects.none()

        try:
            user = CustomUser.objects.get(auth0_id=auth0_id)
            print("🔹 CustomUser encontrado:", user)
        except CustomUser.DoesNotExist:
            print("⚠️ CustomUser no encontrado")
            return Reserva.objects.none()

        if getattr(user, "is_staff", False):
            return Reserva.objects.all()

        if hasattr(user, "doctor_profile"):
            return Reserva.objects.filter(doctor__user=user)

        try:
            paciente = user.paciente_profile
            return Reserva.objects.filter(paciente=paciente).order_by("fecha_hora")
        except Paciente.DoesNotExist:
            return Reserva.objects.none()


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


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def admin_stats(request):
    try:
        week_offset = int(request.GET.get("week_offset", 0))

        today = now().date()
        start_of_week = today + timedelta(weeks=week_offset)
        end_of_week = start_of_week + timedelta(days=6)

        # ✅ Ahora usando los campos correctos
        citas_pendientes = Reserva.objects.filter(estado="pendiente").count()
        citas_semana = Reserva.objects.filter(
            fecha_hora__date__range=[start_of_week, end_of_week], estado="pendiente"
        ).count()
        total_pacientes = Paciente.objects.count()

        return Response(
            {
                "citas_pendientes": citas_pendientes,
                "citas_semana": citas_semana,
                "total_pacientes": total_pacientes,
            }
        )
    except Exception as e:
        return Response({"error": str(e)}, status=500)

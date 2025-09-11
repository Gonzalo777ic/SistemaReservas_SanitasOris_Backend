# appointments/views.py
from django.shortcuts import get_object_or_404

from rest_framework import viewsets, filters, status, mixins, permissions, parsers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from django_filters.rest_framework import DjangoFilterBackend

from .models import Paciente, Doctor, Reserva, CustomUser
from .serializers import (
    PacienteSerializer,
    DoctorSerializer,
    ReservaSerializer,
    HorarioSemanalTemplateSerializer,
    PacienteUpdateSerializer,
    DoctorUpdateSerializer,
)
from .permissions import EsAdmin, EsDoctor, EsPaciente

from django.utils.timezone import now
from django.db.models import Count
from datetime import timedelta, date

from .serializers import (
    ProcedimientoSerializer,
    HorarioDoctorSerializer,
    CustomUserSerializer,
)
from .models import (
    Procedimiento,
    HorarioDoctor,
    HorarioSemanalTemplate,
    HorarioTemplateItem,
)

from rest_framework.views import APIView
from rest_framework.response import Response

from django.utils import timezone
from datetime import datetime, timedelta
from rest_framework.decorators import action

from django.db import transaction


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


# -----------------------------
# Pacientes
# -----------------------------
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
    """
    ViewSet para la gestión de perfiles de doctores.
    """

    queryset = Doctor.objects.all()
    serializer_class = DoctorSerializer
    permission_classes = [IsAuthenticated]

    filter_backends = [filters.SearchFilter]
    search_fields = [
        "user__first_name",
        "user__last_name",
        "user__email",
        "especialidad",
    ]

    def get_permissions(self):
        # This method is now primarily for actions *without* explicit @action permission_classes
        if self.action in ["list", "retrieve"]:
            return [AllowAny()]
        return [
            IsAuthenticated(),
            EsAdmin(),
        ]  # Default for create, update, delete if not overridden

    @action(
        detail=False,
        methods=["get"],
        url_path="by_email/(?P<email>.+)",
        permission_classes=[
            IsAuthenticated,
            EsDoctor,
        ],  # <--- Make sure this is present and correct
    )
    def by_email(self, request, email=None):
        """
        Obtiene el perfil de un doctor por su dirección de correo electrónico.
        """
        try:
            # Obtiene el CustomUser real del usuario que hace la petición
            auth0_id_requesting_user = request.user.payload.get("sub")
            requesting_custom_user = CustomUser.objects.get(
                auth0_id=auth0_id_requesting_user
            )

            # Obtiene el CustomUser del email en la URL
            user_in_url = CustomUser.objects.get(email=email)
            doctor = Doctor.objects.get(user=user_in_url)

            # 💡 Capa de seguridad: un doctor solo puede ver su propio perfil
            if (
                not requesting_custom_user.is_staff
                and requesting_custom_user.email != email
            ):
                return Response(
                    {"error": "No tiene permiso para ver el perfil de otro doctor."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            serializer = self.get_serializer(doctor)
            return Response(serializer.data)
        except CustomUser.DoesNotExist:
            return Response(
                {"error": "Usuario no encontrado."}, status=status.HTTP_404_NOT_FOUND
            )
        except Doctor.DoesNotExist:
            return Response(
                {"error": "Perfil de doctor no encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    # --- Vista para actualizar procedimientos del doctor ---
    @action(
        detail=True,
        methods=["patch"],
        url_path="procedimientos-personalizados",
        permission_classes=[IsAuthenticated, EsDoctor],
    )
    def procedimientos_personalizados(self, request, pk=None):
        """
        Actualiza la lista de procedimientos que un doctor puede realizar.
        """
        try:
            doctor = get_object_or_404(Doctor, pk=pk)
            procedimientos_ids = request.data.get("procedimientos", [])

            # 💡 Capa de seguridad: un doctor solo puede modificar su propio perfil
            auth0_id_requesting_user = request.user.payload.get("sub")
            requesting_custom_user = CustomUser.objects.get(
                auth0_id=auth0_id_requesting_user
            )

            if (
                not requesting_custom_user.is_staff
                and requesting_custom_user.doctor_profile.id != int(pk)
            ):
                return Response(
                    {
                        "error": "No tiene permiso para modificar los procedimientos de otro doctor."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            if not isinstance(procedimientos_ids, list):
                return Response(
                    {"error": "Procedimientos must be a list of IDs."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            with transaction.atomic():
                doctor.procedimientos.set(procedimientos_ids)
                doctor.save()

            return Response(
                {"message": "Procedimientos del doctor actualizados correctamente."},
                status=status.HTTP_200_OK,
            )
        except CustomUser.DoesNotExist:
            return Response(
                {"error": "Usuario no encontrado."}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


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

    @action(detail=False, methods=["get"])
    def disponibilidad(self, request):
        doctor_id = request.query_params.get("doctor_id")
        procedimiento_id = request.query_params.get("procedimiento_id")

        if not doctor_id or not procedimiento_id:
            return Response({"error": "Faltan parámetros"}, status=400)

        try:
            doctor = Doctor.objects.get(id=doctor_id)
            procedimiento = Procedimiento.objects.get(id=procedimiento_id)
        except (Doctor.DoesNotExist, Procedimiento.DoesNotExist):
            return Response(
                {"error": "Doctor o procedimiento no encontrado"}, status=404
            )

        # Ejemplo simple: tomar horarios activos del doctor
        slots = []
        for horario in doctor.horarios.filter(activo=True, dia_semana__gte=0):
            # Aquí podrías generar slots por hora o por duración de procedimiento
            hora_actual = datetime.combine(datetime.today(), horario.hora_inicio)
            hora_fin = datetime.combine(datetime.today(), horario.hora_fin)
            while (
                hora_actual + timedelta(minutes=procedimiento.duracion_min) <= hora_fin
            ):
                slots.append(hora_actual.isoformat())
                hora_actual += timedelta(minutes=procedimiento.duracion_min)

        return Response({"slots_disponibles": slots})


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


class ProcedimientoViewSet(viewsets.ModelViewSet):
    queryset = Procedimiento.objects.all()
    serializer_class = ProcedimientoSerializer

    # CAMBIO CLAVE: Usa el método get_permissions para un control más granular
    def get_permissions(self):
        # Permite a cualquier usuario autenticado ver la lista de procedimientos (métodos GET, OPTIONS)
        if self.action in ["list", "retrieve"]:
            return [permissions.IsAuthenticated()]

        # Requiere ser un usuario administrador para crear, actualizar o eliminar procedimientos
        return [permissions.IsAuthenticated(), permissions.IsAdminUser()]

    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def perform_create(self, serializer):
        doctores_data = self.request.data.getlist("doctores")
        procedimiento_instance = serializer.save()
        procedimiento_instance.doctores.set([int(d_id) for d_id in doctores_data])

    def perform_update(self, serializer):
        doctores_data = self.request.data.getlist("doctores")
        procedimiento_instance = serializer.save()
        procedimiento_instance.doctores.set([int(d_id) for d_id in doctores_data])


class HorarioDoctorViewSet(viewsets.ModelViewSet):
    queryset = HorarioDoctor.objects.all()
    serializer_class = HorarioDoctorSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        doctor_id = self.request.query_params.get("doctor_id")
        if doctor_id:
            qs = qs.filter(doctor_id=doctor_id)

        # Filtro adicional para el admin (si es necesario) o para el doctor
        # Opcional: El frontend puede manejar el filtro para mostrar solo los activos
        # Puedes mantener el filtro para que el GET solo devuelva los activos,
        # pero para PUT, el queryset debe ser all()
        # if self.request.method == 'GET':
        #     return qs.filter(activo=True)

        return qs


class DisponibilidadView(APIView):
    def get(self, request):
        doctor_id = request.query_params.get("doctor_id")
        procedimiento_id = request.query_params.get("procedimiento_id")

        start_date_str = request.query_params.get("start_date")
        end_date_str = request.query_params.get("end_date")

        if not doctor_id or not procedimiento_id:
            return Response(
                {"error": "Debe seleccionar un doctor y un procedimiento."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            doctor = Doctor.objects.get(id=doctor_id)
        except Doctor.DoesNotExist:
            return Response(
                {"error": "El doctor no existe."}, status=status.HTTP_404_NOT_FOUND
            )

        # Parsear las fechas desde los parámetros de la URL.
        try:
            if start_date_str and end_date_str:
                start_date = date.fromisoformat(start_date_str)
                end_date = date.fromisoformat(end_date_str)
            else:
                # Si no se proporcionan fechas, usar la semana actual.
                start_date = date.today()
                end_date = start_date + timedelta(days=6)
        except ValueError:
            return Response(
                {"error": "Formato de fecha inválido. Use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        bloques_disponibles = []
        citas_reservadas = []

        # Encontrar la plantilla de horario semanal activa para el doctor.
        try:
            active_template = HorarioSemanalTemplate.objects.get(
                doctor=doctor, es_activo=True
            )
        except HorarioSemanalTemplate.DoesNotExist:
            return Response(
                {"error": "No hay un horario semanal activo para este doctor."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except HorarioSemanalTemplate.MultipleObjectsReturned:
            return Response(
                {
                    "error": "Hay múltiples horarios activos para este doctor. Contacte al administrador."
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Generar una lista de fechas dentro del rango especificado.
        current_date = start_date
        while current_date <= end_date:
            weekday = current_date.weekday()

            # Filtrar los ítems de la plantilla activa para el día de la semana actual.
            template_items = active_template.items.filter(
                dia_semana=weekday, activo=True
            ).order_by("hora_inicio")

            for item in template_items:
                start_datetime = datetime.combine(current_date, item.hora_inicio)
                end_datetime = datetime.combine(current_date, item.hora_fin)

                bloques_disponibles.append(
                    {
                        "start": start_datetime.isoformat(),
                        "end": end_datetime.isoformat(),
                    }
                )

            current_date += timedelta(days=1)

        # Obtener todas las reservas existentes para el rango de fechas.
        reservas_queryset = Reserva.objects.filter(
            doctor=doctor,
            fecha_hora__gte=start_date,
            fecha_hora__lte=end_date + timedelta(days=1),
        )

        for reserva in reservas_queryset:
            citas_reservadas.append(
                {
                    "start": reserva.fecha_hora.isoformat(),
                    "end": (
                        reserva.fecha_hora + timedelta(minutes=reserva.duracion_min)
                    ).isoformat(),
                }
            )

        return Response(
            {
                "bloques_disponibles": bloques_disponibles,
                "citas_reservadas": citas_reservadas,
            },
            status=status.HTTP_200_OK,
        )


# --- Nuevo ViewSet para Plantillas de Horarios ---


class HorarioSemanalTemplateViewSet(viewsets.ModelViewSet):
    """
    Vista para gestionar plantillas de horarios semanales.
    """

    serializer_class = HorarioSemanalTemplateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Devuelve la lista de plantillas, filtrada por doctor_id si se proporciona.
        """
        queryset = HorarioSemanalTemplate.objects.all()
        doctor_id = self.request.query_params.get("doctor_id", None)
        if doctor_id is not None:
            queryset = queryset.filter(doctor_id=doctor_id)
        return queryset

    @action(detail=True, methods=["post"], url_path="aplicar_a_doctor")
    def aplicar_a_doctor(self, request, pk=None):
        """
        Aplica una plantilla de horario a un doctor, borrando los horarios existentes.
        """
        try:
            template = get_object_or_404(HorarioSemanalTemplate, pk=pk)
            doctor_id = request.data.get("doctor_id")
            if not doctor_id:
                return Response(
                    {"error": "Debe proporcionar un 'doctor_id'"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            with transaction.atomic():
                # Borrar todos los horarios de disponibilidad del doctor
                HorarioDoctor.objects.filter(doctor_id=doctor_id).delete()

                # Crear los nuevos horarios a partir de la plantilla
                # CORRECCIÓN: Usar el related_name "items" del modelo HorarioTemplateItem
                items = template.items.all()
                nuevos_horarios = []
                for item in items:
                    horario_doctor = HorarioDoctor.objects.create(
                        doctor_id=doctor_id,
                        dia_semana=item.dia_semana,
                        hora_inicio=item.hora_inicio,
                        hora_fin=item.hora_fin,
                    )
                    nuevos_horarios.append(horario_doctor)

            # Devolver los nuevos horarios para actualizar el frontend
            serializer = HorarioDoctorSerializer(nuevos_horarios, many=True)
            return Response(
                {
                    "message": "Plantilla aplicada con éxito",
                    "horarios_actualizados": serializer.data,
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=["post"], url_path="activar")
    def activar_plantilla(self, request, pk=None):
        """
        Activa una plantilla semanal para un doctor.
        """
        try:
            # ⭐ CORRECCIÓN CLAVE: Obtener el CustomUser del token
            auth0_id = request.user.payload.get("sub")
            try:
                custom_user = CustomUser.objects.get(auth0_id=auth0_id)
            except CustomUser.DoesNotExist:
                return Response(
                    {"error": "Usuario no encontrado en la base de datos."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # ⭐ CORRECCIÓN: Ahora puedes usar el objeto custom_user para verificar el perfil del doctor
            if not hasattr(custom_user, "doctor_profile"):
                return Response(
                    {"error": "Permisos insuficientes. El usuario no es un doctor."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            template = get_object_or_404(HorarioSemanalTemplate, pk=pk)

            # Verificar que el doctor que intenta activar la plantilla sea su propietario
            if custom_user.doctor_profile != template.doctor:
                return Response(
                    {"error": "No tiene permisos para modificar esta plantilla."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            with transaction.atomic():
                # Desactivar todas las demás plantillas del mismo doctor
                HorarioSemanalTemplate.objects.filter(
                    doctor=template.doctor, es_activo=True
                ).exclude(pk=template.pk).update(es_activo=False)

                # Activar la plantilla seleccionada
                template.es_activo = True
                template.save()

                # Reutilizar la lógica para aplicar la plantilla a los horarios del doctor
                aplicar_response = self.aplicar_a_doctor(request, pk)

            return aplicar_response
        except Exception as e:
            # Manejar errores más específicos si es necesario
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@api_view(["GET"])
@permission_classes([IsAuthenticated, EsDoctor])
def doctor_stats(request):
    """
    Vista para obtener estadísticas de citas y pacientes para un doctor.
    """
    try:
        # Get the CustomUser from the authenticated request
        auth0_id = request.user.payload.get("sub")
        custom_user = CustomUser.objects.get(auth0_id=auth0_id)

        # Get the Doctor profile from the CustomUser
        doctor_profile = Doctor.objects.get(user=custom_user)

        # 1. Correctly filter for PENDING appointments of THIS DOCTOR
        # Use a single, clear filter
        citas_pendientes = Reserva.objects.filter(
            doctor=doctor_profile, estado="pendiente", fecha_hora__gte=timezone.now()
        ).count()

        # 2. Appointments for THIS WEEK for THIS DOCTOR
        week_offset = int(request.GET.get("week_offset", 0))
        today = timezone.now().date()
        start_of_week = (
            today + timedelta(weeks=week_offset) - timedelta(days=today.weekday())
        )
        end_of_week = start_of_week + timedelta(days=6)

        citas_semana = Reserva.objects.filter(
            doctor=doctor_profile, fecha_hora__date__range=[start_of_week, end_of_week]
        ).count()

        # 3. Total unique patients for THIS DOCTOR
        total_pacientes = (
            Reserva.objects.filter(doctor=doctor_profile)
            .values("paciente")
            .distinct()
            .count()
        )

        data = {
            "citas_pendientes": citas_pendientes,
            "citas_semana": citas_semana,
            "total_pacientes": total_pacientes,
        }

        return Response(data, status=status.HTTP_200_OK)

    except (CustomUser.DoesNotExist, Doctor.DoesNotExist):
        return Response(
            {"error": "No se encontró el perfil de doctor."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
@permission_classes([IsAuthenticated, EsDoctor])
def doctor_reservas(request):
    """
    Vista para obtener las reservas del DOCTOR actual para el calendario.
    """
    try:
        auth0_id = request.user.payload.get("sub")
        custom_user = CustomUser.objects.get(auth0_id=auth0_id)
        doctor_profile = Doctor.objects.get(user=custom_user)

        # 4. Filter appointments by doctor and show all (pending and confirmed) for the calendar
        reservas = Reserva.objects.filter(doctor=doctor_profile).order_by("fecha_hora")
        serializer = ReservaSerializer(reservas, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    except (CustomUser.DoesNotExist, Doctor.DoesNotExist):
        return Response(
            {"error": "No se encontró el perfil de doctor."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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

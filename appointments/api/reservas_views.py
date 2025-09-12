# Django Imports
from django.shortcuts import get_object_or_404
from django.utils.timezone import now
from django.db.models import Count
from datetime import datetime, timedelta, date

# DRF Imports
from rest_framework import viewsets, filters, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend

# Project-specific Imports
from ..models import (
    Reserva,
    Paciente,
    Doctor,
    CustomUser,
    Procedimiento,
    HorarioSemanalTemplate,
    HorarioDoctor,
)
from ..serializers import ReservaSerializer
from ..permissions import EsAdmin, EsDoctor, EsPaciente


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

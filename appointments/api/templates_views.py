# Django Imports
from django.shortcuts import get_object_or_404
from django.db import transaction

# DRF Imports
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

# Project-specific Imports
from ..models import HorarioSemanalTemplate, HorarioDoctor, CustomUser, Doctor
from ..serializers import HorarioSemanalTemplateSerializer, HorarioDoctorSerializer


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

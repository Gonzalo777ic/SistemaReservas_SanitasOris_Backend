# Django Imports
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone
from datetime import timedelta

# DRF Imports
from rest_framework import viewsets, filters, status, parsers, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

# Project-specific Imports
from ..models import Doctor, CustomUser, Reserva, Procedimiento
from ..serializers import DoctorSerializer, ReservaSerializer, ProcedimientoSerializer
from ..permissions import EsAdmin, EsDoctor


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


class ProcedimientoViewSet(viewsets.ModelViewSet):
    queryset = Procedimiento.objects.all()
    serializer_class = ProcedimientoSerializer

    def get_permissions(self):
        # Allow any authenticated user to view the list of procedures
        if self.action in ["list", "retrieve"]:
            return [permissions.IsAuthenticated()]

        # For create, update, or delete actions, check if the user is a staff member
        # First, check if the user is authenticated.
        if not self.request.user.is_authenticated:
            return [permissions.IsAuthenticated()]

        # Get the CustomUser from the authenticated request to check the 'is_staff' attribute
        try:
            auth0_id = self.request.user.payload.get("sub")
            user = CustomUser.objects.get(auth0_id=auth0_id)
            if user.is_staff:
                return [
                    permissions.IsAuthenticated()
                ]  # Return success if they are a staff member
        except (CustomUser.DoesNotExist, AttributeError):
            pass  # Continue to the final return statement to deny access

        # Deny access if the user is not a staff member
        return [permissions.IsAdminUser()]

    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def perform_create(self, serializer):
        doctores_data = self.request.data.getlist("doctores")
        procedimiento_instance = serializer.save()
        procedimiento_instance.doctores.set([int(d_id) for d_id in doctores_data])

    def perform_update(self, serializer):
        doctores_data = self.request.data.getlist("doctores")
        procedimiento_instance = serializer.save()
        procedimiento_instance.doctores.set([int(d_id) for d_id in doctores_data])

# appointments/views.py
from rest_framework import viewsets, filters
from .models import Paciente, Doctor, Reserva
from .serializers import PacienteSerializer, DoctorSerializer, ReservaSerializer
from django_filters.rest_framework import DjangoFilterBackend
from .permissions import EsAdmin, EsDoctor, EsPaciente
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import Paciente
from .serializers import PacienteSerializer


class PacienteViewSet(viewsets.ModelViewSet):
    queryset = Paciente.objects.all()
    serializer_class = PacienteSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["nombre", "apellido", "email"]

    def get_permissions(self):
        """
        - Solo admin puede ver/editar pacientes
        """
        user = self.request.user
        if user and user.is_staff:
            return [EsAdmin()]
        return [
            IsAuthenticated()
        ]  # cualquier otro autenticado puede ver solo su perfil

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Paciente.objects.all()
        return Paciente.objects.filter(email=user.email)  # paciente solo ve su ficha


class DoctorViewSet(viewsets.ModelViewSet):
    queryset = Doctor.objects.all()
    serializer_class = DoctorSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["nombre", "apellido", "especialidad", "email"]

    def get_permissions(self):
        """
        - GET (list/retrieve) público (los pacientes necesitan ver doctores para reservar).
        - POST/PUT/DELETE → solo admin.
        """
        if self.action in ["list", "retrieve"]:
            return [AllowAny()]
        return [EsAdmin()]


class ReservaViewSet(viewsets.ModelViewSet):
    queryset = Reserva.objects.all()
    serializer_class = ReservaSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["paciente__id", "doctor__id", "estado"]
    search_fields = ["paciente__nombre", "doctor__nombre"]

    def get_permissions(self):
        """
        - GET → paciente puede ver sus reservas, doctor las suyas, admin todas.
        - POST → solo pacientes autenticados pueden crear.
        - PUT/PATCH/DELETE → restringido según rol.
        """
        if self.action == "create":
            return [EsPaciente()]
        if self.action in ["update", "partial_update", "destroy"]:
            user = self.request.user
            if user.is_staff:
                return [EsAdmin()]
            elif hasattr(user, "doctor_profile"):
                return [EsDoctor()]
            return [EsPaciente()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user

        if not user.is_authenticated:
            return Reserva.objects.none()

        if user.is_staff:
            return Reserva.objects.all()
        if hasattr(user, "doctor_profile"):
            return Reserva.objects.filter(doctor__email=user.email)
        return Reserva.objects.filter(paciente__email=user.email)


@api_view(["GET"])
def get_paciente_by_email(request, email):
    paciente = get_object_or_404(Paciente, email=email)
    serializer = PacienteSerializer(paciente)
    return Response(serializer.data, status=status.HTTP_200_OK)

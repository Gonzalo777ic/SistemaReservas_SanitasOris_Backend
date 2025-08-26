# appointments/views.py
from rest_framework import viewsets, filters
from .models import Paciente, Doctor, Reserva
from .serializers import PacienteSerializer, DoctorSerializer, ReservaSerializer
from django_filters.rest_framework import DjangoFilterBackend
from .permissions import EsAdmin, EsDoctor, EsPaciente


class PacienteViewSet(viewsets.ModelViewSet):
    queryset = Paciente.objects.all()
    serializer_class = PacienteSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["nombre", "apellido", "email"]


class DoctorViewSet(viewsets.ModelViewSet):
    queryset = Doctor.objects.all()
    serializer_class = DoctorSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["nombre", "apellido", "especialidad", "email"]


class ReservaViewSet(viewsets.ModelViewSet):
    queryset = Reserva.objects.all()
    serializer_class = ReservaSerializer

    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["paciente__id", "doctor__id", "estado"]
    search_fields = ["paciente__nombre", "doctor__nombre"]

    def get_permissions(self):
        if self.request.user.is_staff:
            return [EsAdmin()]
        elif hasattr(self.request.user, "doctor_profile"):
            return [EsDoctor()]
        else:
            return [EsPaciente()]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Reserva.objects.all()
        elif hasattr(user, "doctor_profile"):
            return Reserva.objects.filter(doctor__email=user.email)
        else:
            return Reserva.objects.filter(paciente__email=user.email)

from rest_framework import serializers
from .models import Paciente, Doctor, Reserva


class PacienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Paciente
        fields = ["id", "nombre", "apellido", "email", "telefono", "fecha_registro"]


class DoctorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Doctor
        fields = [
            "id",
            "nombre",
            "apellido",
            "especialidad",
            "email",
            "telefono",
            "disponible",
            "fecha_registro",
        ]


class ReservaSerializer(serializers.ModelSerializer):
    paciente = PacienteSerializer(read_only=True)
    doctor = DoctorSerializer(read_only=True)

    paciente_id = serializers.PrimaryKeyRelatedField(
        queryset=Paciente.objects.all(), write_only=True, source="paciente"
    )
    doctor_id = serializers.PrimaryKeyRelatedField(
        queryset=Doctor.objects.all(), write_only=True, source="doctor"
    )

    class Meta:
        model = Reserva
        fields = [
            "id",
            "paciente",
            "doctor",
            "paciente_id",
            "doctor_id",
            "fecha_hora",
            "estado",
            "creado_en",
            "actualizado_en",
        ]

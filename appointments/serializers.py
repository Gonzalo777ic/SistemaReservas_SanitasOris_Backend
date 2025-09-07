from rest_framework import serializers
from .models import CustomUser, Paciente, Doctor, Reserva, Procedimiento, HorarioDoctor


class CustomUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ["id", "first_name", "last_name", "email", "role", "date_joined"]
        read_only_fields = ["id", "date_joined"]


class PacienteSerializer(serializers.ModelSerializer):
    nombre = serializers.CharField(source="user.first_name", read_only=True)
    apellido = serializers.CharField(source="user.last_name", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = Paciente
        fields = ["id", "nombre", "apellido", "email", "telefono", "fecha_registro"]


class DoctorSerializer(serializers.ModelSerializer):
    nombre = serializers.CharField(source="user.first_name", read_only=True)
    apellido = serializers.CharField(source="user.last_name", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)

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
            "procedimientos",
        ]


class ReservaSerializer(serializers.ModelSerializer):
    paciente = serializers.SerializerMethodField(read_only=True)
    doctor = serializers.SerializerMethodField(read_only=True)
    procedimiento = serializers.SerializerMethodField(read_only=True)

    paciente_id = serializers.PrimaryKeyRelatedField(
        queryset=Paciente.objects.all(), write_only=True, source="paciente"
    )
    doctor_id = serializers.PrimaryKeyRelatedField(
        queryset=Doctor.objects.all(), write_only=True, source="doctor"
    )
    procedimiento_id = serializers.PrimaryKeyRelatedField(
        queryset=Procedimiento.objects.all(),
        write_only=True,
        source="procedimiento",
        allow_null=True,
        required=False,
    )

    class Meta:
        model = Reserva
        fields = [
            "id",
            "paciente",
            "doctor",
            "procedimiento",
            "paciente_id",
            "doctor_id",
            "procedimiento_id",
            "fecha_hora",
            "duracion_min",
            "estado",
            "creado_en",
            "actualizado_en",
        ]

    def get_paciente(self, obj):
        user = getattr(obj.paciente, "user", None)
        return {
            "id": obj.paciente.id,
            "nombre": (
                getattr(user, "first_name", "") + " " + getattr(user, "last_name", "")
            ).strip()
            or getattr(user, "email", "Paciente desconocido"),
        }

    def get_doctor(self, obj):
        user = getattr(obj.doctor, "user", None)
        return {
            "id": obj.doctor.id,
            "nombre": (
                getattr(user, "first_name", "") + " " + getattr(user, "last_name", "")
            ).strip()
            or getattr(user, "email", "Doctor desconocido"),
        }

    def get_procedimiento(self, obj):
        if not obj.procedimiento:
            return None
        return {
            "id": obj.procedimiento.id,
            "nombre": obj.procedimiento.nombre,
            "duracion_min": obj.procedimiento.duracion_min,
        }


class ProcedimientoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Procedimiento
        fields = [
            "id",
            "nombre",
            "descripcion",
            "duracion_min",
            "activo",
            "creado_en",
            "actualizado_en",
        ]


class HorarioDoctorSerializer(serializers.ModelSerializer):
    doctor = serializers.SerializerMethodField(read_only=True)
    doctor_id = serializers.PrimaryKeyRelatedField(
        queryset=Doctor.objects.all(), write_only=True, source="doctor"
    )
    dia_nombre = serializers.CharField(source="get_dia_semana_display", read_only=True)

    class Meta:
        model = HorarioDoctor
        fields = [
            "id",
            "doctor",
            "doctor_id",
            "dia_semana",
            "dia_nombre",
            "hora_inicio",
            "hora_fin",
            "activo",
            "creado_en",
            "actualizado_en",
        ]

    def get_doctor(self, obj):
        user = getattr(obj.doctor, "user", None)
        return {
            "id": obj.doctor.id,
            "nombre": (
                getattr(user, "first_name", "") + " " + getattr(user, "last_name", "")
            ).strip()
            or getattr(user, "email", "Doctor desconocido"),
        }

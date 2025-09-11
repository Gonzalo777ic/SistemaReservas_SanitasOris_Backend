from rest_framework import serializers
from .models import (
    CustomUser,
    Paciente,
    Doctor,
    Reserva,
    Procedimiento,
    HorarioDoctor,
    HorarioSemanalTemplate,
    HorarioTemplateItem,
)


from rest_framework import serializers
from .models import (
    CustomUser,
    Paciente,
    Doctor,
    Reserva,
    Procedimiento,
    HorarioDoctor,
    HorarioSemanalTemplate,
    HorarioTemplateItem,
)


class CustomUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ["id", "first_name", "last_name", "email", "role"]


class PacienteSerializer(serializers.ModelSerializer):
    user = CustomUserSerializer(read_only=True)  # <-- Use nested serializer

    class Meta:
        model = Paciente
        fields = ["id", "user", "telefono", "fecha_registro"]


class DoctorSerializer(serializers.ModelSerializer):
    user = CustomUserSerializer(read_only=True)  # <-- Use nested serializer
    procedimientos = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    nombre = serializers.SerializerMethodField()

    class Meta:
        model = Doctor
        fields = [
            "id",
            "user",
            "nombre",
            "especialidad",
            "telefono",
            "disponible",
            "fecha_registro",
            "procedimientos",
        ]

    def get_nombre(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip()


# Serializer para actualizar el teléfono del Paciente
class PacienteUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Paciente
        fields = ["telefono"]


# Serializer para actualizar el teléfono del Doctor
class DoctorUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Doctor
        fields = ["telefono", "especialidad"]


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


class ReservaSerializer(serializers.ModelSerializer):
    # Use nested serializers directly for read operations
    paciente = PacienteSerializer(read_only=True)
    doctor = DoctorSerializer(read_only=True)
    procedimiento = ProcedimientoSerializer(read_only=True)

    # Keep these for write operations (when creating/updating a reservation)
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
            "notas_doctor",
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


# --- Serializers actualizados para Plantillas de Horarios ---


class HorarioTemplateItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = HorarioTemplateItem
        fields = ["dia_semana", "hora_inicio", "hora_fin", "activo"]


class HorarioSemanalTemplateSerializer(serializers.ModelSerializer):
    doctor = serializers.PrimaryKeyRelatedField(queryset=Doctor.objects.all())
    items = HorarioTemplateItemSerializer(many=True, required=False)

    class Meta:
        model = HorarioSemanalTemplate
        # Quitamos los campos que no existen en el modelo de plantilla
        fields = ["id", "nombre", "doctor", "items"]

    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        horario_template = HorarioSemanalTemplate.objects.create(**validated_data)

        for item_data in items_data:
            HorarioTemplateItem.objects.create(template=horario_template, **item_data)

        return horario_template

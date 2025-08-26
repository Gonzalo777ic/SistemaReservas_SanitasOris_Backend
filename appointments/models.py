from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User


class Paciente(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="paciente_profile"
    )

    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    telefono = models.CharField(max_length=15, blank=True, null=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nombre} {self.apellido}"


class Doctor(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="doctor_profile"
    )
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    especialidad = models.CharField(max_length=100)  # Ej: "Ortodoncia", "Endodoncia"
    email = models.EmailField(unique=True)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    disponible = models.BooleanField(default=True)  # si está activo para reservas
    fecha_registro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Dr(a). {self.nombre} {self.apellido} ({self.especialidad})"


class Reserva(models.Model):
    ESTADO_CHOICES = [
        ("pendiente", "Pendiente"),
        ("confirmada", "Confirmada"),
        ("cancelada", "Cancelada"),
    ]

    paciente = models.ForeignKey("Paciente", on_delete=models.CASCADE)
    doctor = models.ForeignKey("Doctor", on_delete=models.CASCADE)
    fecha_hora = models.DateTimeField()
    estado = models.CharField(
        max_length=20, choices=ESTADO_CHOICES, default="pendiente"
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.paciente.nombre} con {self.doctor.nombre} el {self.fecha_hora.strftime('%Y-%m-%d %H:%M')}"

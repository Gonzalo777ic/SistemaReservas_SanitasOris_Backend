from django.db import models
from django.utils import timezone
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)


class CustomUserManager(BaseUserManager):
    def create_user(self, auth0_id, role="paciente", password=None, **extra_fields):
        if not auth0_id:
            raise ValueError("El usuario debe tener un Auth0 ID")

        user = self.model(auth0_id=auth0_id, role=role, **extra_fields)
        user.set_unusable_password()  # nunca guardamos password local
        user.save(using=self._db)
        return user

    def create_superuser(self, auth0_id, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        return self.create_user(
            auth0_id, role="admin", password=password, **extra_fields
        )


class CustomUser(AbstractBaseUser, PermissionsMixin):
    auth0_id = models.CharField(max_length=100, unique=True)  # vínculo con Auth0
    email = models.EmailField(unique=True)  # para login/búsquedas
    first_name = models.CharField(max_length=50, blank=True)
    last_name = models.CharField(max_length=50, blank=True)
    role = models.CharField(
        max_length=20,
        choices=[("paciente", "Paciente"), ("doctor", "Doctor"), ("admin", "Admin")],
        default="paciente",
    )

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = CustomUserManager()

    USERNAME_FIELD = "auth0_id"
    REQUIRED_FIELDS = ["email"]

    def __str__(self):
        return f"{self.email} ({self.role})"


class Paciente(models.Model):
    user = models.OneToOneField(
        "appointments.CustomUser",
        on_delete=models.CASCADE,
        related_name="paciente_profile",
    )

    telefono = models.CharField(max_length=15, blank=True, null=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Paciente ({self.user.auth0_id})"


class Doctor(models.Model):
    user = models.OneToOneField(
        "appointments.CustomUser",
        on_delete=models.CASCADE,
        related_name="doctor_profile",
    )

    especialidad = models.CharField(max_length=100)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    disponible = models.BooleanField(default=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Dr(a). {self.user.auth0_id} ({self.especialidad})"


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
        paciente_nombre = (
            getattr(self.paciente.user, "first_name", "")
            + " "
            + getattr(self.paciente.user, "last_name", "")
        )
        doctor_nombre = (
            getattr(self.doctor.user, "first_name", "")
            + " "
            + getattr(self.doctor.user, "last_name", "")
        )

        paciente_nombre = paciente_nombre.strip() or getattr(
            self.paciente.user, "email", "Paciente desconocido"
        )
        doctor_nombre = doctor_nombre.strip() or getattr(
            self.doctor.user, "email", "Doctor desconocido"
        )

        return f"{paciente_nombre} con Dr(a). {doctor_nombre} el {self.fecha_hora:%Y-%m-%d %H:%M}"

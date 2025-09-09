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
        user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, auth0_id, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        return self.create_user(
            auth0_id, role="admin", password=password, **extra_fields
        )


class CustomUser(AbstractBaseUser, PermissionsMixin):
    auth0_id = models.CharField(max_length=100, unique=True)
    email = models.EmailField(unique=True)
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
    procedimientos = models.ManyToManyField(
        "Procedimiento",
        blank=True,
        related_name="doctores",
    )

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
    procedimiento = models.ForeignKey(
        "Procedimiento", on_delete=models.SET_NULL, null=True, blank=True
    )
    fecha_hora = models.DateTimeField()
    duracion_min = models.PositiveIntegerField(default=30)
    estado = models.CharField(
        max_length=20, choices=ESTADO_CHOICES, default="pendiente"
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    notas_doctor = models.TextField(blank=True, null=True)

    def __str__(self):
        paciente_nombre = (
            getattr(self.paciente.user, "first_name", "")
            + " "
            + getattr(self.paciente.user, "last_name", "")
        ).strip() or getattr(self.paciente.user, "email", "Paciente desconocido")

        doctor_nombre = (
            getattr(self.doctor.user, "first_name", "")
            + " "
            + getattr(self.doctor.user, "last_name", "")
        ).strip() or getattr(self.doctor.user, "email", "Doctor desconocido")

        procedimiento_nombre = (
            self.procedimiento.nombre if self.procedimiento else "Sin procedimiento"
        )

        return f"{paciente_nombre} con Dr(a). {doctor_nombre} el {self.fecha_hora:%Y-%m-%d %H:%M} ({procedimiento_nombre})"


class Procedimiento(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)
    duracion_min = models.PositiveIntegerField(
        help_text="Duración estándar del procedimiento en minutos"
    )
    activo = models.BooleanField(default=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.nombre} ({self.duracion_min} min)"


class HorarioDoctor(models.Model):
    DIAS_SEMANA = [
        (0, "Lunes"),
        (1, "Martes"),
        (2, "Miércoles"),
        (3, "Jueves"),
        (4, "Viernes"),
        (5, "Sábado"),
        (6, "Domingo"),
    ]

    doctor = models.ForeignKey(
        "Doctor", on_delete=models.CASCADE, related_name="horarios"
    )
    dia_semana = models.IntegerField(choices=DIAS_SEMANA)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    activo = models.BooleanField(default=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("doctor", "dia_semana", "hora_inicio", "hora_fin")
        ordering = ["doctor", "dia_semana", "hora_inicio"]

    def __str__(self):
        return f"{self.doctor} - {self.get_dia_semana_display()} {self.hora_inicio} a {self.hora_fin}"


# ... (código anterior)


class HorarioSemanalTemplate(models.Model):
    doctor = models.ForeignKey(
        "Doctor", on_delete=models.CASCADE, related_name="horario_templates"
    )
    nombre = models.CharField(max_length=100)
    es_activo = models.BooleanField(
        default=False,
        help_text="Indica si esta plantilla es la actualmente activa para el doctor.",
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("doctor", "nombre")

    def __str__(self):
        return f"Plantilla '{self.nombre}' de {self.doctor}"


class HorarioTemplateItem(models.Model):
    """
    Representa una única franja horaria dentro de una plantilla.
    """

    DIAS_SEMANA = [
        (0, "Lunes"),
        (1, "Martes"),
        (2, "Miércoles"),
        (3, "Jueves"),
        (4, "Viernes"),
        (5, "Sábado"),
        (6, "Domingo"),
    ]

    template = models.ForeignKey(
        "HorarioSemanalTemplate", on_delete=models.CASCADE, related_name="items"
    )
    dia_semana = models.IntegerField(choices=DIAS_SEMANA)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    activo = models.BooleanField(
        default=True,
        help_text="Indica si el bloque de horario está activo y debe mostrarse.",
    )

    class Meta:
        ordering = ["dia_semana", "hora_inicio"]

    def __str__(self):
        return f"Día {self.get_dia_semana_display()} de {self.hora_inicio} a {self.hora_fin}"

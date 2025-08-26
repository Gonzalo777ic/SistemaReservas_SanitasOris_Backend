from django.contrib import admin
from .models import Paciente, Doctor, Reserva

@admin.register(Paciente)
class PacienteAdmin(admin.ModelAdmin):
    list_display = ("nombre", "apellido", "email", "telefono", "fecha_registro")
    search_fields = ("nombre", "apellido", "email")

@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ("nombre", "apellido", "especialidad", "email", "disponible", "fecha_registro")
    search_fields = ("nombre", "apellido", "especialidad", "email")
    list_filter = ("especialidad", "disponible")

@admin.register(Reserva)
class ReservaAdmin(admin.ModelAdmin):
    list_display = ("paciente", "doctor", "fecha_hora", "estado", "creado_en", "actualizado_en")
    search_fields = ("paciente__nombre", "doctor__nombre")
    list_filter = ("estado", "fecha_hora", "doctor__especialidad")

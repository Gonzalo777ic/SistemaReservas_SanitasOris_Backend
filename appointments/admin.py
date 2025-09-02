from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Paciente, Doctor, Reserva, CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = (
        "email",
        "auth0_id",
        "first_name",
        "last_name",
        "role",
        "is_staff",
        "is_superuser",
    )
    list_filter = ("role", "is_staff", "is_superuser", "is_active")
    search_fields = ("email", "auth0_id", "first_name", "last_name")
    ordering = ("email",)

    fieldsets = (
        (None, {"fields": ("auth0_id", "email", "password")}),
        (
            "Personal info",
            {"fields": ("first_name", "last_name", "role")},
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (
            "Important dates",
            {"fields": ("last_login", "date_joined")},
        ),
    )

    readonly_fields = ("date_joined", "last_login")  # 👈 SOLUCIÓN

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "auth0_id",
                    "email",
                    "role",
                    "password1",
                    "password2",
                    "is_staff",
                    "is_superuser",
                ),
            },
        ),
    )


@admin.register(Paciente)
class PacienteAdmin(admin.ModelAdmin):
    list_display = (
        "get_nombre",
        "get_apellido",
        "get_email",
        "telefono",
        "fecha_registro",
    )

    def get_nombre(self, obj):
        return obj.user.first_name if hasattr(obj.user, "first_name") else "-"

    get_nombre.short_description = "Nombre"

    def get_apellido(self, obj):
        return obj.user.last_name if hasattr(obj.user, "last_name") else "-"

    get_apellido.short_description = "Apellido"

    def get_email(self, obj):
        return obj.user.email if hasattr(obj.user, "email") else "-"

    get_email.short_description = "Email"


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = (
        "get_nombre",
        "get_apellido",
        "get_email",
        "especialidad",
        "telefono",
        "disponible",
    )

    def get_nombre(self, obj):
        return obj.user.first_name if hasattr(obj.user, "first_name") else "-"

    get_nombre.short_description = "Nombre"

    def get_apellido(self, obj):
        return obj.user.last_name if hasattr(obj.user, "last_name") else "-"

    get_apellido.short_description = "Apellido"

    def get_email(self, obj):
        return obj.user.email if hasattr(obj.user, "email") else "-"

    get_email.short_description = "Email"


@admin.register(Reserva)
class ReservaAdmin(admin.ModelAdmin):
    list_display = ("paciente", "doctor", "fecha_hora", "estado", "creado_en")

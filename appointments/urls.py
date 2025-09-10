from django.urls import path, include
from rest_framework import routers
from .views import (
    PacienteViewSet,
    DoctorViewSet,
    ReservaViewSet,
    ProcedimientoViewSet,
    HorarioDoctorViewSet,
    get_paciente_by_email,
    sync_user,
    whoami,
    admin_stats,
    DisponibilidadView,
    CustomUserViewSet,
    HorarioSemanalTemplateViewSet,
    doctor_stats,
    doctor_reservas,
    update_profile,
)
from .views import admin_stats

router = routers.DefaultRouter()
router.register(r"pacientes", PacienteViewSet, basename="paciente")
router.register(r"doctores", DoctorViewSet)
router.register(r"reservas", ReservaViewSet)
router.register(r"procedimientos", ProcedimientoViewSet)
router.register(r"horarios", HorarioDoctorViewSet)
router.register(r"users", CustomUserViewSet, basename="user")
router.register(
    r"horarios-semanales", HorarioSemanalTemplateViewSet, basename="horarios-semanales"
)

urlpatterns = [
    path("", include(router.urls)),
    path(
        "pacientes/by_email/<str:email>/",
        get_paciente_by_email,
        name="get_paciente_by_email",
    ),
    path("sync-user/", sync_user, name="sync_user"),
    path("whoami/", whoami, name="whoami"),
    path("admin/stats/", admin_stats, name="admin_stats"),
    path(
        "reservas/disponibilidad/", DisponibilidadView.as_view(), name="disponibilidad"
    ),
    path("doctor/stats/", doctor_stats, name="doctor_stats"),
    path("doctor/reservas/", doctor_reservas, name="doctor_reservas"),
    path("profile/update/", update_profile, name="update_profile"),
]

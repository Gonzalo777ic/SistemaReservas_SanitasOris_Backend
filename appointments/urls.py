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
)
from .views import admin_stats

router = routers.DefaultRouter()
router.register(r"pacientes", PacienteViewSet, basename="paciente")
router.register(r"doctores", DoctorViewSet)
router.register(r"reservas", ReservaViewSet)
router.register(r"procedimientos", ProcedimientoViewSet)
router.register(r"horarios", HorarioDoctorViewSet)
router.register(r"users", CustomUserViewSet, basename="user")

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
]

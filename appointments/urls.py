# appointments/urls.py
from django.urls import path, include
from rest_framework import routers
from .views import (
    PacienteViewSet,
    DoctorViewSet,
    ReservaViewSet,
    get_paciente_by_email,
    sync_user,
    whoami,
)
from .views import admin_stats

router = routers.DefaultRouter()
router.register(r"pacientes", PacienteViewSet)
router.register(r"doctores", DoctorViewSet)
router.register(r"reservas", ReservaViewSet)

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
]

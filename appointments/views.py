# appointments/views.py

from .api.auth_views import CustomUserViewSet, sync_user, whoami, update_profile
from .api.patients_views import PacienteViewSet, get_paciente_by_email
from .api.doctor_views import (
    DoctorViewSet,
    doctor_stats,
    doctor_reservas,
    ProcedimientoViewSet,
)
from .api.reservas_views import ReservaViewSet, DisponibilidadView, admin_stats
from .api.templates_views import HorarioSemanalTemplateViewSet, HorarioDoctorViewSet

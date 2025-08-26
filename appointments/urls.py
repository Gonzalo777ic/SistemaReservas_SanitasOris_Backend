from django.urls import path, include
from rest_framework import routers
from .views import PacienteViewSet, DoctorViewSet, ReservaViewSet

router = routers.DefaultRouter()
router.register(r"pacientes", PacienteViewSet)
router.register(r"doctores", DoctorViewSet)
router.register(r"reservas", ReservaViewSet)

urlpatterns = [
    path("", include(router.urls)),
]

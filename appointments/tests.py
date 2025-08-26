from django.test import TestCase
from rest_framework.test import APIClient
from django.contrib.auth.models import User
from .models import Paciente, Doctor, Reserva
from rest_framework import status
from datetime import datetime, timedelta


class ReservaAPITest(TestCase):
    def setUp(self):
        # Crear usuarios
        self.admin_user = User.objects.create_superuser(
            username="admin", password="adminpass"
        )
        self.doctor_user = User.objects.create_user(
            username="doctor", password="doctorpass"
        )
        self.paciente_user = User.objects.create_user(
            username="paciente", password="pacientepass"
        )

        # Crear perfiles
        self.doctor_profile = Doctor.objects.create(
            user=self.doctor_user,
            nombre="Doc",
            apellido="Uno",
            especialidad="Ortodoncia",
            email="doctor@test.com",
        )

        self.paciente_profile = Paciente.objects.create(
            user=self.paciente_user,
            nombre="Pac",
            apellido="Uno",
            email="paciente@test.com",
        )

        # Crear reservas
        self.reserva = Reserva.objects.create(
            paciente=self.paciente_profile,
            doctor=self.doctor_profile,
            fecha_hora=datetime.now() + timedelta(days=1),
        )

        self.client = APIClient()

    def test_admin_access_all_reservas(self):
        self.client.login(username="admin", password="adminpass")
        response = self.client.get("/api/reservas/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_doctor_can_only_see_own_reservas(self):
        self.client.force_authenticate(user=self.doctor_user)
        response = self.client.get("/api/reservas/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Aquí validamos que el doctor solo ve reservas que le corresponden
        for r in response.data:
            self.assertEqual(r["doctor"]["email"], "doctor@test.com")

    def test_paciente_can_only_see_own_reservas(self):
        self.client.force_authenticate(user=self.paciente_user)
        response = self.client.get("/api/reservas/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for r in response.data:
            self.assertEqual(r["paciente"]["email"], "paciente@test.com")

# appointments/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CustomUser, Doctor, Paciente


@receiver(post_save, sender=CustomUser)
def create_related_profile(sender, instance, created, **kwargs):
    # Si el rol cambió a doctor y no existe un Doctor, lo creamos
    if instance.role == "doctor":
        Doctor.objects.get_or_create(user=instance)

    # Si el rol cambió a paciente y no existe un Paciente, lo creamos
    elif instance.role == "paciente":
        Paciente.objects.get_or_create(user=instance)

    # Si el rol cambió a admin, opcional: podrías borrar las otras relaciones

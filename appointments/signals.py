# appointments/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CustomUser, Doctor, Paciente

# Si decides tener un modelo Administrador:
# from .models import Administrador


@receiver(post_save, sender=CustomUser)
def create_related_profile(sender, instance, created, **kwargs):
    """
    Cada vez que se crea o actualiza un CustomUser,
    se asegura que exista el perfil correspondiente según su rol.
    """
    # Doctor
    if instance.role == "doctor":
        Doctor.objects.get_or_create(user=instance)

    # Paciente
    elif instance.role == "paciente":
        Paciente.objects.get_or_create(user=instance)

    # Admin
    elif instance.role == "admin":
        # Opción 1: si solo usas is_staff
        if not instance.is_staff:
            instance.is_staff = True
            instance.save(update_fields=["is_staff"])

        # Opción 2 (si tienes un modelo Administrador con más info)
        # Administrador.objects.get_or_create(user=instance)

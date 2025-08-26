from rest_framework.permissions import BasePermission, SAFE_METHODS


class EsAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_staff


class EsDoctor(BasePermission):
    def has_permission(self, request, view):
        return hasattr(request.user, "doctor_profile")

    def has_object_permission(self, request, view, obj):
        return obj.doctor.email == request.user.email


class EsPaciente(BasePermission):
    def has_permission(self, request, view):
        return hasattr(request.user, "paciente_profile")

    def has_object_permission(self, request, view, obj):
        return obj.paciente.email == request.user.email

# /Users/triguna/Documents/Development/Projects/AI_medical_appointment/appointments/apps.py
from django.apps import AppConfig


class AppointmentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'appointments'
    verbose_name = 'Medical Appointments'

    def ready(self):
        import appointments.signals  # noqa
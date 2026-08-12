# appointments/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Appointment
from .services import EmailService, SMSService, CalendarService
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Appointment)
def handle_appointment_saved(sender, instance, created, **kwargs):
    """
    Handle post-save signals for Appointment model.
    Send notifications when a new appointment is created or status changes.
    """
    if created:
        logger.info(f"New appointment created: {instance.id}")
        # Send notifications for new appointments
        EmailService.send_appointment_confirmation(instance)
        EmailService.send_doctor_notification(instance)
        SMSService.send_appointment_confirmation(instance)
        CalendarService.save_ics(instance)
    else:
        # Check if status changed to 'confirmed'
        if instance.status == 'confirmed' and not instance.confirmed_at:
            instance.confirmed_at = timezone.now()
            instance.save(update_fields=['confirmed_at'])
            logger.info(f"Appointment {instance.id} confirmed")
            EmailService.send_appointment_confirmation(instance)
            SMSService.send_appointment_confirmation(instance)
        elif instance.status == 'cancelled':
            logger.info(f"Appointment {instance.id} cancelled")
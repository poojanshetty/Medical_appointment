# appointments/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Appointment
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Appointment)
def handle_appointment_saved(sender, instance, created, **kwargs):
    """
    Log appointment save events. Actual notification sending (email/SMS/ICS)
    is handled explicitly in the views to avoid duplicate sends.
    """
    if created:
        logger.info(f"New appointment created: {instance.id} (status={instance.status})")
    else:
        if instance.status == 'cancelled':
            logger.info(f"Appointment {instance.id} cancelled")
        elif instance.status == 'confirmed':
            logger.info(f"Appointment {instance.id} confirmed")
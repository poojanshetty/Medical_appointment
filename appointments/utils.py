import re
import logging
from datetime import datetime, timedelta
from django.utils import timezone

logger = logging.getLogger(__name__)


def validate_email(email):
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_phone(phone):
    """Validate phone number (10-15 digits)."""
    phone_clean = re.sub(r'\D', '', phone)
    return 10 <= len(phone_clean) <= 15


def parse_date(date_str):
    """Parse date from various formats."""
    formats = [
        '%Y-%m-%d',
        '%d/%m/%Y',
        '%m/%d/%Y',
        '%d-%m-%Y',
        '%Y/%m/%d',
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    return None


def parse_time(time_str):
    """Parse time from various formats."""
    formats = [
        '%H:%M',
        '%I:%M %p',
        '%I:%M%p',
        '%H.%M',
        '%I.%M %p',
    ]
    for fmt in formats:
        try:
            return datetime.strptime(time_str.strip(), fmt).time()
        except ValueError:
            continue
    return None


def get_available_slots(doctor, date, for_priority=False):
    """
    Get available time slots for a doctor on a given date.
    The very first slot of the day is reserved for priority bookings only,
    unless for_priority=True is passed (used for priority patients).
    """
    from .models import Appointment

    slots = []
    current = datetime.combine(date, doctor.available_from)
    end = datetime.combine(date, doctor.available_to)
    first_slot_time = current.time()

    while current < end:
        time_slot = current.time()

        # Reserve the first slot of the day for priority patients only
        if time_slot == first_slot_time and not for_priority:
            current += timedelta(minutes=30)
            continue

        if not Appointment.objects.filter(
                doctor=doctor,
                appointment_date=date,
                appointment_time=time_slot,
                status__in=['pending', 'confirmed']
        ).exists():
            slots.append(time_slot)
        current += timedelta(minutes=30)

    return slots


def get_appointment_stats():
    """Get overall appointment statistics."""
    from .models import Appointment, Doctor

    today = timezone.now().date()
    total = Appointment.objects.count()
    confirmed = Appointment.objects.filter(status='confirmed').count()
    pending = Appointment.objects.filter(status='pending').count()
    completed = Appointment.objects.filter(status='completed').count()
    cancelled = Appointment.objects.filter(status='cancelled').count()
    today_appointments = Appointment.objects.filter(appointment_date=today).count()
    today_confirmed = Appointment.objects.filter(
        appointment_date=today,
        status='confirmed'
    ).count()

    return {
        'total': total,
        'confirmed': confirmed,
        'pending': pending,
        'completed': completed,
        'cancelled': cancelled,
        'today': today_appointments,
        'today_confirmed': today_confirmed,
        'total_doctors': Doctor.objects.filter(is_active=True).count(),
    }


def get_doctor_availability_summary(doctor):
    """Get a summary of a doctor's availability."""
    from .models import Appointment

    today = timezone.now().date()
    next_week = today + timedelta(days=7)

    appointments = Appointment.objects.filter(
        doctor=doctor,
        appointment_date__gte=today,
        appointment_date__lte=next_week,
        status__in=['pending', 'confirmed']
    ).values('appointment_date', 'appointment_time')

    booked_slots = {}
    for appt in appointments:
        date_str = appt['appointment_date'].isoformat()
        time_str = appt['appointment_time'].strftime('%H:%M')
        booked_slots.setdefault(date_str, []).append(time_str)

    return booked_slots


def format_appointment_duration(start_time, duration_minutes=30):
    """Format appointment duration."""
    end = (datetime.combine(datetime.today(), start_time) +
           timedelta(minutes=duration_minutes)).time()
    return end


def calculate_patient_age(birth_date):
    """Calculate age from birth date."""
    today = timezone.now().date()
    return today.year - birth_date.year - (
            (today.month, today.day) < (birth_date.month, birth_date.day)
    )


def doctor_status(request):
    """Makes is_doctor / is_hospital_admin available in every template automatically."""
    is_doctor = False
    is_hospital_admin = False
    if request.user.is_authenticated:
        is_doctor = request.user.groups.filter(name='Doctors').exists()
        is_hospital_admin = request.user.groups.filter(name='HospitalAdmins').exists()
    return {'is_doctor': is_doctor, 'is_hospital_admin': is_hospital_admin}
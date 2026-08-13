from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

GENDER_CHOICES = [
    ('M', 'Male'),
    ('F', 'Female'),
    ('O', 'Other'),
]


class Doctor(models.Model):
    """Doctor model with specialization and availability."""
    name = models.CharField(max_length=100)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True, null=True)
    specialization = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=15)
    available_days = models.CharField(max_length=100, default='Mon,Tue,Wed,Thu,Fri')
    available_from = models.TimeField(default='09:00')
    available_to = models.TimeField(default='17:00')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_available_days_display(self):
        """Return a human-readable availability label for the doctor."""
        day_map = {
            'Mon': 'Monday',
            'Tue': 'Tuesday',
            'Wed': 'Wednesday',
            'Thu': 'Thursday',
            'Fri': 'Friday',
            'Sat': 'Saturday',
            'Sun': 'Sunday',
        }

        days = [day.strip() for day in self.available_days.split(',') if day.strip()]
        if not days:
            return 'Not specified'

        labels = [day_map.get(day, day) for day in days]
        if labels == ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']:
            return 'Monday to Friday'
        return ', '.join(labels)

    def __str__(self):
        return f"Dr. {self.name} ({self.specialization})"

    class Meta:
        ordering = ['name']


class Patient(models.Model):
    """Patient model with contact details."""
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ]
    name = models.CharField(max_length=100)
    age = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(150)])
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    phone = models.CharField(max_length=15)
    email = models.EmailField()
    address = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.age}, {self.get_gender_display()})"


class Appointment(models.Model):
    """Appointment model linking patient and doctor."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('rejected', 'Rejected'),
        ('rescheduled', 'Rescheduled'),
    ]
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='appointments')
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='appointments')
    appointment_date = models.DateField()
    appointment_time = models.TimeField()
    problem_description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(blank=True, null=True)
    voice_booking = models.BooleanField(default=False)
    is_priority = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.patient.name} with Dr. {self.doctor.name} on {self.appointment_date} at {self.appointment_time}"

    class Meta:
        ordering = ['appointment_date', 'appointment_time']
        unique_together = ['doctor', 'appointment_date', 'appointment_time']

    def get_status_display_color(self):
        colors = {
            'pending': 'warning',
            'confirmed': 'success',
            'completed': 'info',
            'cancelled': 'danger',
            'rescheduled': 'secondary',
        }
        return colors.get(self.status, 'primary')
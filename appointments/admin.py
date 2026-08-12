from django.contrib import admin
from .models import Doctor, Patient, Appointment

@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ['name', 'specialization', 'gender', 'email', 'phone', 'is_active']
    list_filter = ['specialization', 'gender', 'is_active']
    search_fields = ['name', 'specialization', 'email']

@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ['name', 'age', 'gender', 'phone', 'email']
    list_filter = ['gender']
    search_fields = ['name', 'phone', 'email']

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ['patient', 'doctor', 'appointment_date', 'appointment_time', 'status', 'is_priority']
    list_filter = ['status', 'appointment_date', 'doctor', 'is_priority']
    search_fields = ['patient__name', 'doctor__name', 'problem_description']
    date_hierarchy = 'appointment_date'
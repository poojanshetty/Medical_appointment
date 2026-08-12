import json
import logging
from datetime import datetime, timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from .models import Doctor, Patient, Appointment
from .services import EmailService, SMSService, CalendarService, ExcelService
from .utils import get_appointment_stats, get_available_slots, parse_date, parse_time
from django.contrib import messages

logger = logging.getLogger(__name__)


def is_doctor(user):
    return user.is_authenticated and user.groups.filter(name='Doctors').exists()


def index(request):
    """Home page."""
    doctors = Doctor.objects.filter(is_active=True)
    recent_appointments = Appointment.objects.filter(
        status__in=['confirmed', 'pending']
    ).order_by('-created_at')[:10]

    stats = get_appointment_stats()

    context = {
        'doctors': doctors,
        'recent_appointments': recent_appointments,
        'stats': stats,
    }
    return render(request, 'appointments/index.html', context)


def voice_booking(request):
    """Backward-compatible redirect: the app now uses manual booking only."""
    return redirect('appointments:manual_booking')


@csrf_exempt
@require_http_methods(['POST'])
def voice_book_appointment(request):
    """API endpoint for voice booking."""
    try:
        data = json.loads(request.body)

        name = data.get('name', '').strip()
        age = data.get('age', '').strip()
        gender = data.get('gender', '').strip()
        problem = data.get('problem', '').strip()
        doctor_name = data.get('doctor', '').strip()
        date_str = data.get('date', '').strip()
        time_str = data.get('time', '').strip()
        phone = data.get('phone', '').strip()
        email = data.get('email', '').strip()

        missing_fields = []
        if not name: missing_fields.append('name')
        if not age: missing_fields.append('age')
        if not gender: missing_fields.append('gender')
        if not problem: missing_fields.append('problem')
        if not doctor_name: missing_fields.append('doctor')
        if not date_str: missing_fields.append('date')
        if not time_str: missing_fields.append('time')
        if not phone: missing_fields.append('phone')
        if not email: missing_fields.append('email')

        if missing_fields:
            return JsonResponse({
                'success': False,
                'error': 'Missing required fields.',
                'missing_fields': missing_fields
            }, status=400)

        doctor = Doctor.objects.filter(name__icontains=doctor_name, is_active=True).first()
        if not doctor:
            available = ', '.join([d.name for d in Doctor.objects.filter(is_active=True)])
            return JsonResponse({
                'success': False,
                'error': f'Doctor "{doctor_name}" not found. Available: {available}'
            }, status=400)

        appointment_date = parse_date(date_str)
        if not appointment_date:
            return JsonResponse({
                'success': False,
                'error': 'Invalid date format. Use YYYY-MM-DD or DD/MM/YYYY.'
            }, status=400)

        # Restrict voice booking to today or tomorrow only
        today = timezone.now().date()
        tomorrow = today + timedelta(days=1)
        if appointment_date not in (today, tomorrow):
            return JsonResponse({
                'success': False,
                'error': 'Voice booking is only available for today or tomorrow.'
            }, status=400)

        appointment_time = parse_time(time_str)
        if not appointment_time:
            return JsonResponse({
                'success': False,
                'error': 'Invalid time format. Use HH:MM (24-hour) or HH:MM AM/PM.'
            }, status=400)

        # First slot of the day is reserved for priority bookings; voice booking is never priority
        if appointment_time == doctor.available_from:
            return JsonResponse({
                'success': False,
                'error': 'That slot is reserved for priority patients. Please choose another time.'
            }, status=400)

        if Appointment.objects.filter(
                doctor=doctor,
                appointment_date=appointment_date,
                appointment_time=appointment_time,
                status__in=['pending', 'confirmed']
        ).exists():
            return JsonResponse({
                'success': False,
                'error': f'Slot already booked with Dr. {doctor.name} on {appointment_date} at {appointment_time}.'
            }, status=400)

        patient = Patient.objects.create(
            name=name,
            age=int(age),
            gender=gender[0].upper() if gender else 'M',
            phone=phone,
            email=email
        )

        appointment = Appointment.objects.create(
            patient=patient,
            doctor=doctor,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            problem_description=problem,
            status='confirmed',
            confirmed_at=timezone.now(),
            voice_booking=True
        )

        email_sent = EmailService.send_appointment_confirmation(appointment)
        EmailService.send_doctor_notification(appointment)
        sms_sent = SMSService.send_appointment_confirmation(appointment)

        ics_path = CalendarService.save_ics(appointment)

        return JsonResponse({
            'success': True,
            'appointment_id': appointment.id,
            'message': f'Appointment booked with Dr. {doctor.name} on {appointment_date} at {appointment_time}',
            'patient_name': patient.name,
            'doctor_name': doctor.name,
            'date': appointment_date.strftime('%d/%m/%Y'),
            'time': appointment_time.strftime('%I:%M %p'),
            'email_sent': email_sent,
            'sms_sent': sms_sent,
            'ics_path': str(ics_path) if ics_path else None,
        })

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON format.'}, status=400)
    except ValueError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    except Exception as e:
        logger.error(f"Voice booking error: {str(e)}")
        return JsonResponse({'success': False, 'error': f'Server error: {str(e)}'}, status=500)


@csrf_exempt
def synthesize_speech(request):
    """API endpoint: takes text, returns MP3 audio using Google Cloud TTS."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    try:
        from .services import TTSService
        data = json.loads(request.body)
        text = data.get('text', '').strip()

        if not text:
            return JsonResponse({'error': 'No text provided'}, status=400)

        audio_content = TTSService.synthesize_speech(text)

        return HttpResponse(audio_content, content_type='audio/mpeg')

    except Exception as e:
        logger.error(f"TTS synthesis error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


def get_doctor_slots(request, doctor_id):
    """Get available slots for a doctor."""
    doctor = get_object_or_404(Doctor, id=doctor_id)
    date_str = request.GET.get('date')
    is_priority = request.GET.get('priority', 'false').lower() == 'true'

    if not date_str:
        return JsonResponse({'error': 'Date required'}, status=400)

    date_obj = parse_date(date_str)
    if not date_obj:
        return JsonResponse({'error': 'Invalid date'}, status=400)

    slots = get_available_slots(doctor, date_obj, for_priority=is_priority)
    slots_str = [s.strftime('%I:%M %p') for s in slots]

    return JsonResponse({
        'doctor': doctor.name,
        'date': date_obj.strftime('%d/%m/%Y'),
        'slots': slots_str
    })


@csrf_exempt
@require_http_methods(['POST'])
def check_availability(request):
    """Check if a time slot is available."""
    try:
        data = json.loads(request.body)
        doctor_id = data.get('doctor_id')
        date_str = data.get('date')
        time_str = data.get('time')

        doctor = get_object_or_404(Doctor, id=doctor_id)
        date_obj = parse_date(date_str)
        time_obj = parse_time(time_str)

        if not date_obj or not time_obj:
            return JsonResponse({'available': False, 'error': 'Invalid date/time'})

        exists = Appointment.objects.filter(
            doctor=doctor,
            appointment_date=date_obj,
            appointment_time=time_obj,
            status__in=['pending', 'confirmed']
        ).exists()

        return JsonResponse({
            'available': not exists,
            'doctor': doctor.name,
            'date': date_obj.strftime('%d/%m/%Y'),
            'time': time_obj.strftime('%I:%M %p')
        })
    except Exception as e:
        return JsonResponse({'available': False, 'error': str(e)})


def dashboard(request):
    """Admin dashboard with statistics."""
    doctors = Doctor.objects.filter(is_active=True)
    today = timezone.now().date()

    stats = get_appointment_stats()
    today_appointments = Appointment.objects.filter(appointment_date=today)

    upcoming = Appointment.objects.filter(
        appointment_date__gte=today,
        status__in=['confirmed', 'pending']
    ).order_by('appointment_date', 'appointment_time')[:20]

    doctor_stats = []
    for doctor in doctors:
        doc_appointments = doctor.appointments.filter(status='confirmed')
        doctor_stats.append({
            'doctor': doctor,
            'total': doc_appointments.count(),
            'today': doc_appointments.filter(appointment_date=today).count(),
        })

    context = {
        'doctors': doctors,
        'doctor_stats': doctor_stats,
        'stats': stats,
        'today_appointments': today_appointments,
        'upcoming': upcoming,
    }
    return render(request, 'appointments/dashboard.html', context)


def doctor_list(request):
    """List all doctors."""
    doctors = Doctor.objects.filter(is_active=True)
    return render(request, 'appointments/doctor_list.html', {'doctors': doctors})


def doctor_detail(request, doctor_id):
    """Doctor detail with appointments."""
    doctor = get_object_or_404(Doctor, id=doctor_id)
    appointments = doctor.appointments.all().order_by('-appointment_date', '-appointment_time')

    context = {
        'doctor': doctor,
        'appointments': appointments,
    }
    return render(request, 'appointments/doctor_detail.html', context)


def appointments_list(request):
    """List all appointments with filters."""
    status_filter = request.GET.get('status', '')
    doctor_filter = request.GET.get('doctor', '')
    date_filter = request.GET.get('date', '')

    appointments = Appointment.objects.all().order_by('-appointment_date', '-appointment_time')

    if status_filter:
        appointments = appointments.filter(status=status_filter)
    if doctor_filter:
        appointments = appointments.filter(doctor_id=doctor_filter)
    if date_filter:
        date_obj = parse_date(date_filter)
        if date_obj:
            appointments = appointments.filter(appointment_date=date_obj)

    doctors = Doctor.objects.filter(is_active=True)

    context = {
        'appointments': appointments,
        'doctors': doctors,
        'status_filter': status_filter,
        'doctor_filter': doctor_filter,
        'date_filter': date_filter,
        'is_doctor': is_doctor(request.user),
    }
    return render(request, 'appointments/appointments_list.html', context)


def export_page(request):
    """Export page with options."""
    doctors = Doctor.objects.filter(is_active=True)
    return render(request, 'appointments/export.html', {'doctors': doctors})


def export_doctor_excel(request, doctor_id):
    """Export doctor's appointments to Excel."""
    doctor = get_object_or_404(Doctor, id=doctor_id)
    filepath, filename = ExcelService.generate_doctor_report(doctor)

    with open(filepath, 'rb') as f:
        response = HttpResponse(f.read(),
                                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


def export_all_excel(request):
    """Export all appointments to Excel."""
    filepath, filename = ExcelService.generate_all_doctors_report()

    with open(filepath, 'rb') as f:
        response = HttpResponse(f.read(),
                                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


def download_ics(request, appointment_id):
    """Download ICS file for appointment."""
    appointment = get_object_or_404(Appointment, id=appointment_id)
    ics_content = CalendarService.generate_ics(appointment)

    response = HttpResponse(ics_content, content_type='text/calendar')
    response['Content-Disposition'] = f'attachment; filename="appointment_{appointment_id}.ics"'
    return response


@login_required
@user_passes_test(is_doctor)
@require_http_methods(['POST'])
def confirm_appointment(request, appointment_id):
    """Confirm an appointment."""
    appointment = get_object_or_404(Appointment, id=appointment_id)
    appointment.status = 'confirmed'
    appointment.confirmed_at = timezone.now()
    appointment.save()

    EmailService.send_appointment_confirmation(appointment)
    SMSService.send_appointment_confirmation(appointment)

    messages.success(request, f'Appointment confirmed for {appointment.patient.name}.')
    return redirect('appointments:appointments_list')


@login_required
@user_passes_test(is_doctor)
@require_http_methods(['POST'])
def cancel_appointment(request, appointment_id):
    """Cancel an appointment."""
    appointment = get_object_or_404(Appointment, id=appointment_id)
    appointment.status = 'cancelled'
    appointment.save()

    EmailService.send_cancellation_email(appointment)

    messages.info(request, f'Appointment cancelled for {appointment.patient.name}.')
    return redirect('appointments:appointments_list')


@require_http_methods(['POST'])
def reschedule_appointment(request, appointment_id):
    """Reschedule an appointment."""
    appointment = get_object_or_404(Appointment, id=appointment_id)
    new_date_str = request.POST.get('new_date')
    new_time_str = request.POST.get('new_time')

    if not new_date_str or not new_time_str:
        messages.error(request, 'Please provide new date and time.')
        return redirect('appointments:appointments_list')

    new_date = parse_date(new_date_str)
    new_time = parse_time(new_time_str)

    if not new_date or not new_time:
        messages.error(request, 'Invalid date or time format.')
        return redirect('appointments:appointments_list')

    if Appointment.objects.filter(
            doctor=appointment.doctor,
            appointment_date=new_date,
            appointment_time=new_time,
            status__in=['pending', 'confirmed']
    ).exclude(id=appointment.id).exists():
        messages.error(request, 'New slot is already booked.')
        return redirect('appointments:appointments_list')

    appointment.appointment_date = new_date
    appointment.appointment_time = new_time
    appointment.status = 'rescheduled'
    appointment.save()

    EmailService.send_appointment_confirmation(appointment)
    SMSService.send_appointment_confirmation(appointment)

    messages.success(request, f'Appointment rescheduled for {appointment.patient.name}.')
    return redirect('appointments:appointments_list')


def manual_booking(request):
    """
    Manual appointment booking page with calendar and time slot selection.
    Supports pre-selecting a doctor via ?doctor_id=<id> (e.g. from the doctor's profile page).
    """
    doctors = Doctor.objects.filter(is_active=True)

    doctor_list = [
        {
            'id': d.id,
            'name': d.name,
            'specialization': d.specialization,
            'available_from': d.available_from.strftime('%H:%M') if d.available_from else '09:00',
            'available_to': d.available_to.strftime('%H:%M') if d.available_to else '17:00',
        }
        for d in doctors
    ]

    selected_doctor_id = request.GET.get('doctor_id', '')

    context = {
        'doctors': doctors,
        'doctor_list_json': json.dumps(doctor_list),
        'selected_doctor_id': selected_doctor_id,
    }
    return render(request, 'appointments/manual_booking.html', context)


@csrf_exempt
@require_http_methods(['POST'])
def book_manual_appointment(request):
    """
    API endpoint for manual booking from the form.
    """
    try:
        doctor_id = request.POST.get('doctor_id')
        name = request.POST.get('name', '').strip()
        age = request.POST.get('age', '').strip()
        gender = request.POST.get('gender', '').strip()
        problem = request.POST.get('problem', '').strip()
        date_str = request.POST.get('date', '').strip()
        time_str = request.POST.get('time', '').strip()
        phone = request.POST.get('phone', '').strip()
        email = request.POST.get('email', '').strip()
        is_priority = request.POST.get('is_priority') == 'on'

        missing_fields = []
        if not doctor_id: missing_fields.append('doctor')
        if not name: missing_fields.append('name')
        if not age: missing_fields.append('age')
        if not gender: missing_fields.append('gender')
        if not problem: missing_fields.append('problem')
        if not date_str: missing_fields.append('date')
        if not time_str: missing_fields.append('time')
        if not phone: missing_fields.append('phone')
        if not email: missing_fields.append('email')

        if missing_fields:
            messages.error(request, f'Missing fields: {", ".join(missing_fields)}')
            return redirect('appointments:manual_booking')

        doctor = get_object_or_404(Doctor, id=doctor_id, is_active=True)

        appointment_date = parse_date(date_str)
        if not appointment_date:
            messages.error(request, 'Invalid date format. Please use YYYY-MM-DD.')
            return redirect('appointments:manual_booking')

        appointment_time = parse_time(time_str)
        if not appointment_time:
            messages.error(request, 'Invalid time format.')
            return redirect('appointments:manual_booking')

        # Enforce: first slot of the day is reserved for priority bookings only
        if appointment_time == doctor.available_from and not is_priority:
            messages.error(request, 'This slot is reserved for priority patients. Please choose another time.')
            return redirect('appointments:manual_booking')

        if Appointment.objects.filter(
                doctor=doctor,
                appointment_date=appointment_date,
                appointment_time=appointment_time,
                status__in=['pending', 'confirmed']
        ).exists():
            messages.error(request, 'Slot is no longer available. Please select another time.')
            return redirect('appointments:manual_booking')

        patient = Patient.objects.create(
            name=name,
            age=int(age),
            gender=gender[0].upper() if gender else 'M',
            phone=phone,
            email=email
        )

        appointment = Appointment.objects.create(
            patient=patient,
            doctor=doctor,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            problem_description=problem,
            status='confirmed',
            confirmed_at=timezone.now(),
            voice_booking=False,
            is_priority=is_priority,
        )

        EmailService.send_appointment_confirmation(appointment)
        EmailService.send_doctor_notification(appointment)
        SMSService.send_appointment_confirmation(appointment)
        CalendarService.save_ics(appointment)

        messages.success(
            request,
            f'✅ Appointment booked with Dr. {doctor.name} on {appointment_date.strftime("%d/%m/%Y")} at {appointment_time.strftime("%I:%M %p")}'
        )
        return redirect('appointments:booking_confirmation', appointment_id=appointment.id)

    except ValueError as e:
        messages.error(request, f'Error: {str(e)}')
        return redirect('appointments:manual_booking')
    except Exception as e:
        logger.error(f"Manual booking error: {str(e)}")
        messages.error(request, f'Server error: {str(e)}')
        return redirect('appointments:manual_booking')


def booking_confirmation(request, appointment_id):
    """Show a confirmation page after successful booking."""
    appointment = get_object_or_404(Appointment, id=appointment_id)
    context = {
        'appointment': appointment,
    }
    return render(request, 'appointments/booking_confirmation.html', context)
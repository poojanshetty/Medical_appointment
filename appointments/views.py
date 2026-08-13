import json
import logging
from datetime import datetime, timedelta
from django.db.models import Q
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import LoginView
from django.contrib.auth.models import User, Group
from django.urls import reverse
from django.utils import timezone
from .models import Doctor, Patient, Appointment
from .services import EmailService, SMSService, CalendarService, ExcelService
from .utils import get_appointment_stats, get_available_slots, parse_date, parse_time
from django.contrib import messages

logger = logging.getLogger(__name__)


def is_doctor(user):
    return user.is_authenticated and user.groups.filter(name='Doctors').exists()


def get_doctor_for_user(user):
    """Resolve the doctor profile linked to the current doctor login."""
    if not user or not user.is_authenticated or not is_doctor(user):
        return None

    doctor = Doctor.objects.filter(email__iexact=(user.email or '')).first()
    if doctor:
        return doctor

    username_normalized = ''.join(ch for ch in (user.username or '').lower() if ch.isalnum())
    if not username_normalized:
        return None

    for candidate in Doctor.objects.filter(is_active=True):
        name_normalized = ''.join(ch for ch in candidate.name.lower() if ch.isalnum())
        if not name_normalized:
            continue
        if username_normalized.endswith(name_normalized) or name_normalized.endswith(username_normalized) or username_normalized == name_normalized:
            return candidate

    return Doctor.objects.filter(name__icontains=user.username).first()


class DoctorLoginView(LoginView):
    """Doctor-only login page."""
    template_name = 'appointments/doctor_login.html'
    redirect_authenticated_user = True

    def form_valid(self, form):
        user = form.get_user()
        if not user.groups.filter(name='Doctors').exists():
            form.add_error(None, 'This account is not registered as a doctor.')
            return self.form_invalid(form)
        login(self.request, user)
        return redirect(self.get_success_url())


class CustomerLoginView(LoginView):
    """Customer login page for regular users."""
    template_name = 'appointments/customer_login.html'
    redirect_authenticated_user = True

    def form_valid(self, form):
        user = form.get_user()
        if user.groups.filter(name='Doctors').exists():
            form.add_error(None, 'This account is for doctors. Please use the doctor login.')
            return self.form_invalid(form)
        login(self.request, user)
        return redirect(self.get_success_url())


def customer_register(request):
    """Customer registration page for regular users."""
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')
        name = request.POST.get('name', '').strip()
        phone = request.POST.get('phone', '').strip()
        age = request.POST.get('age', '').strip()
        gender = request.POST.get('gender', '').strip()
        address = request.POST.get('address', '').strip()

        if not all([username, email, password1, password2, name, phone, age, gender]):
            messages.error(request, 'Please fill in all required fields.')
            return redirect('appointments:customer_register')

        if password1 != password2:
            messages.error(request, 'Passwords do not match.')
            return redirect('appointments:customer_register')

        if User.objects.filter(username__iexact=username).exists():
            messages.error(request, 'This username is already taken.')
            return redirect('appointments:customer_register')

        if User.objects.filter(email__iexact=email).exists():
            messages.error(request, 'This email is already registered.')
            return redirect('appointments:customer_register')

        user = User.objects.create_user(username=username, email=email, password=password1)
        user.first_name = name.split()[0] if name else username
        user.last_name = ' '.join(name.split()[1:]) if name else ''
        user.save(update_fields=['first_name', 'last_name'])

        customer_group, _ = Group.objects.get_or_create(name='Customers')
        user.groups.add(customer_group)

        Patient.objects.create(
            name=name,
            age=int(age),
            gender=gender,
            phone=phone,
            email=email,
            address=address,
        )

        login(request, user)
        messages.success(request, 'Customer account created successfully.')
        return redirect('appointments:manual_booking')

    return render(request, 'appointments/customer_register.html')


def index(request):
    """Home page."""
    doctors = Doctor.objects.filter(is_active=True)

    is_customer = request.user.is_authenticated and not is_doctor(request.user)

    if is_customer:
        patient = Patient.objects.filter(email__iexact=request.user.email).first()
        if patient:
            recent_appointments = Appointment.objects.filter(patient=patient).order_by('-created_at')[:10]
        else:
            recent_appointments = Appointment.objects.none()
    else:
        recent_appointments = Appointment.objects.filter(
            status__in=['confirmed', 'pending']
        ).order_by('-created_at')[:10]

    stats = get_appointment_stats()

    context = {
        'doctors': doctors,
        'recent_appointments': recent_appointments,
        'stats': stats,
        'is_doctor': is_doctor(request.user),
        'is_customer': is_customer,
    }
    return render(request, 'appointments/index.html', context)


def clinic_contact(request):
    """Public clinic contact page with contact details."""
    clinic = {
        'name': 'MedCare Clinic',
        'email': 'care@medcareclinic.com',
        'phone': '+1 (555) 014-2026',
        'address': '45 Health Avenue, Suite 220, New York, NY',
        'hours': 'Mon - Sat: 9:00 AM - 7:00 PM',
    }
    context = {
        'clinic': clinic,
        'is_doctor': is_doctor(request.user),
    }
    return render(request, 'appointments/clinic_contact.html', context)


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

        patient = Patient.objects.filter(email__iexact=email).first()
        if patient is None:
            patient = Patient.objects.create(
                name=name,
                age=int(age),
                gender=gender[0].upper() if gender else 'M',
                phone=phone,
                email=email,
            )
        else:
            patient.name = name
            patient.age = int(age)
            patient.gender = gender[0].upper() if gender else patient.gender
            patient.phone = phone
            patient.save(update_fields=['name', 'age', 'gender', 'phone'])

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


@login_required
def doctor_list(request):
    """Contact page by role: doctors see customer contacts, customers are redirected away."""
    if not request.user.is_authenticated:
        return redirect('appointments:index')

    if is_doctor(request.user):
        doctor = get_doctor_for_user(request.user)
        if not doctor:
            return redirect('appointments:index')

        patients = Patient.objects.filter(appointments__doctor=doctor).distinct().order_by('name')
        context = {
            'patients': patients,
            'doctors': [],
            'is_doctor': True,
            'show_customer_contacts': True,
        }
        return render(request, 'appointments/doctor_list.html', context)

    return redirect('appointments:index')


@login_required
@user_passes_test(is_doctor)
def doctor_detail(request, doctor_id):
    """Doctor detail with appointments. Restricted to doctors only."""
    doctor = get_object_or_404(Doctor, id=doctor_id)
    appointments = doctor.appointments.all().order_by('-appointment_date', '-appointment_time')

    context = {
        'doctor': doctor,
        'appointments': appointments,
        'is_doctor': True,
        'logged_doctor': get_doctor_for_user(request.user),
    }
    return render(request, 'appointments/doctor_detail.html', context)


@login_required
def appointments_list(request):
    """List appointments; doctors see all assigned bookings, customers see only their own."""
    status_filter = request.GET.get('status', '')
    doctor_filter = request.GET.get('doctor', '')
    date_filter = request.GET.get('date', '')

    appointments = Appointment.objects.all().order_by('-appointment_date', '-appointment_time')

    if is_doctor(request.user):
        logged_doctor = get_doctor_for_user(request.user)
        if logged_doctor:
            appointments = appointments.filter(doctor=logged_doctor)
            doctor_filter = str(logged_doctor.id)
    else:
        patient = Patient.objects.filter(email__iexact=request.user.email).first()
        if patient:
            appointments = appointments.filter(patient=patient)
        else:
            appointments = appointments.none()

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
        'logged_doctor': get_doctor_for_user(request.user) if is_doctor(request.user) else None,
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
    logged_doctor = get_doctor_for_user(request.user)
    if logged_doctor and appointment.doctor.id != logged_doctor.id:
        messages.error(request, 'You can only manage your own appointments.')
        return redirect('appointments:appointments_list')

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
def complete_appointment(request, appointment_id):
    """Mark an appointment as completed and save any doctor's notes/history."""
    appointment = get_object_or_404(Appointment, id=appointment_id)
    logged_doctor = get_doctor_for_user(request.user)
    if logged_doctor and appointment.doctor.id != logged_doctor.id:
        messages.error(request, 'You can only manage your own appointments.')
        return redirect('appointments:appointments_list')

    notes = request.POST.get('notes', '').strip()
    if notes:
        appointment.notes = notes

    appointment.status = 'completed'
    appointment.save(update_fields=['notes', 'status'])

    messages.success(request, f'Appointment marked as completed for {appointment.patient.name}.')
    return redirect('appointments:appointments_list')


@login_required
@user_passes_test(is_doctor)
@require_http_methods(['POST'])
def cancel_appointment(request, appointment_id):
    """Cancel an appointment."""
    appointment = get_object_or_404(Appointment, id=appointment_id)
    logged_doctor = get_doctor_for_user(request.user)
    if logged_doctor and appointment.doctor.id != logged_doctor.id:
        messages.error(request, 'You can only manage your own appointments.')
        return redirect('appointments:appointments_list')

    appointment.status = 'cancelled'
    appointment.save()

    EmailService.send_cancellation_email(appointment)

    messages.info(request, f'Appointment cancelled for {appointment.patient.name}.')
    return redirect('appointments:appointments_list')


@login_required
@user_passes_test(is_doctor)
@require_http_methods(['POST'])
def reject_appointment(request, appointment_id):
    """Reject an appointment and keep it visible in the list for the doctor."""
    appointment = get_object_or_404(Appointment, id=appointment_id)
    logged_doctor = get_doctor_for_user(request.user)
    if logged_doctor and appointment.doctor.id != logged_doctor.id:
        messages.error(request, 'You can only manage your own appointments.')
        return redirect('appointments:appointments_list')

    appointment.status = 'rejected'
    appointment.save()

    messages.warning(request, f'Appointment rejected for {appointment.patient.name}.')
    return redirect('appointments:appointments_list')


@login_required
@user_passes_test(is_doctor)
@require_http_methods(['POST'])
def reschedule_appointment(request, appointment_id):
    """Reschedule an appointment; cancelled/rejected appointments can be moved again."""
    appointment = get_object_or_404(Appointment, id=appointment_id)
    logged_doctor = get_doctor_for_user(request.user)
    if logged_doctor and appointment.doctor.id != logged_doctor.id:
        messages.error(request, 'You can only manage your own appointments.')
        return redirect('appointments:appointments_list')

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
            status__in=['pending', 'confirmed', 'rescheduled']
    ).exclude(id=appointment.id).exists():
        messages.error(request, 'New slot is already booked.')
        return redirect('appointments:appointments_list')

    appointment.appointment_date = new_date
    appointment.appointment_time = new_time
    appointment.status = 'pending' if appointment.status in ['cancelled', 'rejected', 'rescheduled'] else 'rescheduled'
    appointment.save()

    EmailService.send_appointment_confirmation(appointment)
    SMSService.send_appointment_confirmation(appointment)

    messages.success(request, f'Appointment rescheduled for {appointment.patient.name}.')
    return redirect('appointments:appointments_list')


@login_required
@user_passes_test(is_doctor)
@require_http_methods(['POST'])
def update_appointment_notes(request, appointment_id):
    """Save patient condition/notes for an appointment."""
    appointment = get_object_or_404(Appointment, id=appointment_id)
    logged_doctor = get_doctor_for_user(request.user)
    if logged_doctor and appointment.doctor.id != logged_doctor.id:
        messages.error(request, 'You can only manage your own appointments.')
        return redirect('appointments:appointments_list')

    notes = request.POST.get('notes', '').strip()
    appointment.notes = notes
    appointment.save(update_fields=['notes'])
    messages.success(request, f'Condition notes saved for {appointment.patient.name}.')
    return redirect('appointments:appointments_list')


@login_required
def manual_booking(request):
    """
    Manual appointment booking page with calendar and time slot selection.
    Supports pre-selecting a doctor via ?doctor_id=<id> (e.g. from the doctor's profile page).
    """
    if is_doctor(request.user):
        messages.error(request, 'Doctors cannot book appointments from the customer panel.')
        return redirect('appointments:dashboard')

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
        'is_doctor': is_doctor(request.user),
    }
    return render(request, 'appointments/manual_booking.html', context)


@login_required
@csrf_exempt
@require_http_methods(['POST'])
def book_manual_appointment(request):
    """
    API endpoint for manual booking from the form.
    """
    if is_doctor(request.user):
        return JsonResponse({'success': False, 'error': 'Doctors cannot book from the customer flow.'}, status=403)

    try:
        doctor_id = request.POST.get('doctor_id')
        problem = request.POST.get('problem', '').strip()
        date_str = request.POST.get('date', '').strip()
        time_str = request.POST.get('time', '').strip()
        is_priority = request.POST.get('is_priority') == 'on'

        if request.user.is_authenticated:
            patient = Patient.objects.filter(email__iexact=request.user.email).first()
            if patient is None:
                patient = Patient.objects.filter(name__iexact=request.user.get_full_name() or request.user.username).first()
            if patient is None:
                messages.error(request, 'Customer profile not found. Please register again.')
                return redirect('appointments:customer_register')
            name = patient.name
            age = patient.age
            gender = patient.gender
            phone = patient.phone
            email = patient.email
        else:
            name = ''
            age = ''
            gender = ''
            phone = ''
            email = ''

        missing_fields = []
        if not doctor_id: missing_fields.append('doctor')
        if not problem: missing_fields.append('problem')
        if not date_str: missing_fields.append('date')
        if not time_str: missing_fields.append('time')

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

        patient = Patient.objects.filter(email__iexact=email).first()
        if patient is None:
            patient = Patient.objects.create(
                name=name,
                age=int(age),
                gender=gender[0].upper() if gender else 'M',
                phone=phone,
                email=email,
            )
        else:
            patient.name = name
            patient.age = int(age)
            patient.gender = gender[0].upper() if gender else patient.gender
            patient.phone = phone
            patient.save(update_fields=['name', 'age', 'gender', 'phone'])

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
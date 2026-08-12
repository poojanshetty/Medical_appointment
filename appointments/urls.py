from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'appointments'

urlpatterns = [
    # Auth
    path('login/', auth_views.LoginView.as_view(template_name='appointments/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # Public pages
    path('', views.index, name='index'),
    path('voice-booking/', views.voice_booking, name='voice_booking'),
    path('manual-booking/', views.manual_booking, name='manual_booking'),

    # API endpoints
    path('api/voice-book/', views.voice_book_appointment, name='voice_book'),
    path('api/manual-book/', views.book_manual_appointment, name='book_manual_appointment'),
    path('api/doctor-slots/<int:doctor_id>/', views.get_doctor_slots, name='doctor_slots'),
    path('api/check-availability/', views.check_availability, name='check_availability'),
    path('api/synthesize-speech/', views.synthesize_speech, name='synthesize_speech'),

    # Dashboard & Reports
    path('dashboard/', views.dashboard, name='dashboard'),
    path('export/', views.export_page, name='export_page'),
    path('export/doctor/<int:doctor_id>/', views.export_doctor_excel, name='export_doctor_excel'),
    path('export/all/', views.export_all_excel, name='export_all_excel'),
    path('export/ics/<int:appointment_id>/', views.download_ics, name='download_ics'),

    # Doctors
    path('doctors/', views.doctor_list, name='doctor_list'),
    path('doctors/<int:doctor_id>/', views.doctor_detail, name='doctor_detail'),

    # Appointments
    path('appointments/', views.appointments_list, name='appointments_list'),
    path('appointments/<int:appointment_id>/confirm/', views.confirm_appointment, name='confirm_appointment'),
    path('appointments/<int:appointment_id>/cancel/', views.cancel_appointment, name='cancel_appointment'),
    path('appointments/<int:appointment_id>/reschedule/', views.reschedule_appointment, name='reschedule_appointment'),
    path('appointments/<int:appointment_id>/confirmation/', views.booking_confirmation, name='booking_confirmation'),
]
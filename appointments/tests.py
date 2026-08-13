from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from appointments.models import Appointment, Doctor, Patient


class BasicAppointmentModelTests(TestCase):
    def test_doctor_and_appointment_can_be_created(self):
        doctor = Doctor.objects.create(
            name='Joshi',
            specialization='Gynecology',
            email='dr.joshi@clinic.com',
            phone='+919900000001',
            available_days='Mon,Tue,Wed,Thu,Fri',
            is_active=True,
        )
        patient = Patient.objects.create(
            name='Test Patient',
            age=30,
            gender='F',
            phone='+919900000002',
            email='patient@example.com',
        )

        appointment = Appointment.objects.create(
            patient=patient,
            doctor=doctor,
            appointment_date='2026-08-12',
            appointment_time='10:00:00',
            problem_description='Need review',
            status='pending',
        )

        self.assertEqual(appointment.doctor.name, 'Joshi')
        self.assertEqual(appointment.patient.name, 'Test Patient')
        self.assertEqual(appointment.status, 'pending')

    def test_appointment_can_be_rejected_by_doctor(self):
        doctor = Doctor.objects.create(
            name='Joshi',
            specialization='Gynecology',
            email='dr.joshi@clinic.com',
            phone='+919900000003',
            available_days='Mon,Tue,Wed,Thu,Fri',
            is_active=True,
        )
        patient = Patient.objects.create(
            name='Reject Patient',
            age=26,
            gender='M',
            phone='+919900000004',
            email='rejectpatient@example.com',
        )
        appointment = Appointment.objects.create(
            patient=patient,
            doctor=doctor,
            appointment_date='2026-08-14',
            appointment_time='11:00:00',
            problem_description='Needs follow-up',
            status='confirmed',
        )

        doctor_group, _ = Group.objects.get_or_create(name='Doctors')
        doctor_user = User.objects.create_user(username='joshi', email='dr.joshi@clinic.com', password='secret123')
        doctor_user.groups.add(doctor_group)

        self.client.force_login(doctor_user)
        response = self.client.post(reverse('appointments:reject_appointment', args=[appointment.id]))

        self.assertEqual(response.status_code, 302)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, 'rejected')

    def test_doctor_can_mark_appointment_as_completed_with_history(self):
        doctor = Doctor.objects.create(
            name='Joshi',
            specialization='Gynecology',
            email='dr.joshi@clinic.com',
            phone='+919900000005',
            available_days='Mon,Tue,Wed,Thu,Fri',
            is_active=True,
        )
        patient = Patient.objects.create(
            name='Completed Patient',
            age=32,
            gender='F',
            phone='+919900000006',
            email='completedpatient@example.com',
        )
        appointment = Appointment.objects.create(
            patient=patient,
            doctor=doctor,
            appointment_date='2026-08-15',
            appointment_time='12:00:00',
            problem_description='Consultation',
            status='confirmed',
            notes='Initial observations',
        )

        doctor_group, _ = Group.objects.get_or_create(name='Doctors')
        doctor_user = User.objects.create_user(username='joshi2', email='dr.joshi2@clinic.com', password='secret123')
        doctor_user.groups.add(doctor_group)

        self.client.force_login(doctor_user)
        response = self.client.post(
            reverse('appointments:complete_appointment', args=[appointment.id]),
            {'notes': 'Patient responded well to treatment and follow-up advised.'},
        )

        self.assertEqual(response.status_code, 302)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, 'completed')
        self.assertIn('follow-up', appointment.notes)

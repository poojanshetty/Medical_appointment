from django.core.management.base import BaseCommand
from appointments.models import Doctor


class Command(BaseCommand):
    help = 'Seed initial doctor data'

    def handle(self, *args, **options):
        doctors = [
            {'name': 'Sharma', 'specialization': 'Cardiology', 'email': 'dr.sharma@clinic.com', 'phone': '+919876543210', 'gender': 'M'},
            {'name': 'Patel', 'specialization': 'Neurology', 'email': 'dr.patel@clinic.com', 'phone': '+919876543211', 'gender': 'M'},
            {'name': 'Kumar', 'specialization': 'Orthopedics', 'email': 'dr.kumar@clinic.com', 'phone': '+919876543212', 'gender': 'M'},
            {'name': 'Singh', 'specialization': 'Pediatrics', 'email': 'dr.singh@clinic.com', 'phone': '+919876543213', 'gender': 'M'},
            {'name': 'Reddy', 'specialization': 'Dermatology', 'email': 'dr.reddy@clinic.com', 'phone': '+919876543214', 'gender': 'F'},
            {'name': 'Joshi', 'specialization': 'Gynecology', 'email': 'dr.joshi@clinic.com', 'phone': '+919876543215', 'gender': 'F'},
        ]

        for doc_data in doctors:
            Doctor.objects.get_or_create(
                name=doc_data['name'],
                defaults={
                    'specialization': doc_data['specialization'],
                    'email': doc_data['email'],
                    'phone': doc_data['phone'],
                    'gender': doc_data['gender'],
                    'is_active': True,
                }
            )
            self.stdout.write(self.style.SUCCESS(f"Created Doctor: {doc_data['name']}"))

        self.stdout.write(self.style.SUCCESS("✅ Seed data created successfully!"))
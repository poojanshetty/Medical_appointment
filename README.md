# Medical Appointment System

A Django-based medical appointment platform for managing doctor bookings, patient appointments, role-based login, and clinic contact information.

## Overview

This project allows:

- customers to register and book appointments
- doctors to log in and manage their assigned appointments
- clinic staff to monitor patient and appointment data
- role-based access control between doctor and customer accounts
- contact and support information for the clinic

## Features

- Doctor and customer authentication flows
- Doctor-specific appointment management
- Patient registration and profile creation
- Appointment booking, confirmation, cancellation, rejection, and rescheduling
- Appointment status tracking
- Dashboard for appointment summaries
- Clinic contact page with email, phone number, address, and opening hours
- Role-based navigation and restricted access
- Modern responsive UI

## Tech Stack

- Python 3
- Django 4.2
- SQLite database
- Bootstrap 5
- Font Awesome Icons

## Project Structure

```bash
AI_medical_appointment/
├── ai_medical_appointment/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── appointments/
│   ├── templates/
│   ├── static/
│   ├── migrations/
│   ├── management/
│   ├── models.py
│   ├── services.py
│   ├── urls.py
│   ├── utils.py
│   ├── views.py
│   └── admin.py
├── db.sqlite3
├── manage.py
├── requirements.txt
├── README.md
└── venv/
```

## Prerequisites

Before running the application, make sure you have:

- Python 3.10 or later
- pip
- virtual environment support

## Installation

1. Clone the repository:

```bash
git clone <repository-url>
cd AI_medical_appointment
```

2. Create and activate a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Apply database migrations:

```bash
python manage.py migrate
```

5. Create a superuser for admin access:

```bash
python manage.py createsuperuser
```

6. Run the development server:

```bash
python manage.py runserver
```

Then open:

```text
http://127.0.0.1:8000/
```

## Default Access

The app supports two main login roles:

### Doctor Login

Use a doctor account created in the Doctors group.

### Customer Login

Use a customer account created through customer registration.

## Seed Data

If you want demo records, run:

```bash
python manage.py seed_data
```

This command populates the database with sample doctors and appointment data.

## Common Commands

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
python manage.py check
```

## Environment Notes

- The project uses SQLite by default for local development.
- Static and template files are organized under the appointments app.
- The app is designed to run locally without external services required.

## License

This project is for educational and local development use.

## Contact

For project questions or support, contact the clinic contact information available from the app or update the details in the clinic contact page.


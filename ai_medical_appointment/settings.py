# /Users/triguna/Documents/Development/Projects/AI_medical_appointment/ai_medical_appointment/settings.py
from pathlib import Path
import certifi
import os


os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(BASE_DIR / 'gcp-credentials.json')


SECRET_KEY = 'django-insecure-your-secret-key-here-change-in-production'

DEBUG = True


BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-your-secret-key-here-change-in-production'

DEBUG = True

ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'crispy_forms',
    'crispy_bootstrap5',
    'appointments',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'ai_medical_appointment.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'appointments.utils.doctor_status',
            ],
        },
    },
]

WSGI_APPLICATION = 'ai_medical_appointment.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'

USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# Email settings (update with your SMTP)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'poojaniranjanshetty@gmail.com'
EMAIL_HOST_PASSWORD = 'lbwt hfif ynxh fytg'

# SMS settings (using Twilio or mock)
TWILIO_ACCOUNT_SID = 'AC859fb1b67383fd99e14c5873f3f00670'
TWILIO_AUTH_TOKEN = '97e54a2092c25d9b881b1d5f2fd6bf1e'
TWILIO_PHONE_NUMBER = '+919916073885'
SMS_MOCK = True  # Set to False to use Twilio

# App settings
APP_NAME = 'Medical Appointment System'
ADMIN_EMAIL = 'pooja.ai.appointment@gmail.com'

LOGIN_URL = 'appointments:login'
LOGIN_REDIRECT_URL = 'appointments:index'
LOGOUT_REDIRECT_URL = 'appointments:index'
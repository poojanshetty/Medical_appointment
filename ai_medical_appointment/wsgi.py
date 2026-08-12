# /Users/triguna/Documents/Development/Projects/AI_medical_appointment/ai_medical_appointment/wsgi.py
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_medical_appointment.settings')
application = get_wsgi_application()
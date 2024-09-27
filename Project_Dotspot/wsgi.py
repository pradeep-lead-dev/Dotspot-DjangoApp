"""
WSGI config for Project_Dotspot project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/wsgi/
"""

import os , threading

from django.core.wsgi import get_wsgi_application
from dashboard.views import  start_model_processing
from workflow.views import start_watching
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Project_Dotspot.settings')

application = get_wsgi_application()


videopath =  os.path.join(os.path.dirname(__file__), 'model/orange1.mp4') 


# start_model_processing()
start_watching()


"""
WSGI config for Project_Dotspot project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/wsgi/
"""

import os , threading

from django.core.wsgi import get_wsgi_application
from dashboard.views import  start_model_processing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Project_Dotspot.settings')

application = get_wsgi_application()


videopath =  os.path.join(os.path.dirname(__file__), 'model/orange1.mp4') 

# camera_urls = [
#     "rtsp://admin:Admin@123@115.244.221.74:2025/H.264",
#     "rtsp://admin:Admin@123@115.244.221.74:2025/H.264",
#       # Add more camera URLs
# ]
# Start processing all camera streams simultaneously
# processing_thread = threading.Thread(target=startmodel, args=(camera_urls,), daemon=True)
# processing_thread = threading.Thread(target=start_model_processing, daemon=True)
# processing_thread.start()
start_model_processing()

from django.urls import path
from .views import *
# import views

urlpatterns = [

    path('/send-notification',trigger),
    path('/calculate-weight',calculate_weight),
    path('/change-camera-details',change_camera_details),

    ]
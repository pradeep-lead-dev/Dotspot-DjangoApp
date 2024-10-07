from django.urls import path
from .views import *
# import views

urlpatterns = [
    path('', HomeView.as_view(),name="home"),
    path('/video/<str:camera_id>/', VideoFeed.as_view(),name="video"),
    path('/start-camera',start_camera),
    path('/stop-camera',stop_camera),
        # path('/check', ),

    ]
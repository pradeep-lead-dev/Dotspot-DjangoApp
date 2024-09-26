from django.urls import path
from .views import *
# import views

urlpatterns = [
    path('', HomeView.as_view(),name="home"),
    path('/video/<str:camera_no>/', VideoFeed.as_view(),name="video"),
        # path('/check', ),

    ]
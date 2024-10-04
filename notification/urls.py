from django.urls import path
from .views import *
# import views

urlpatterns = [

    path('/sendmail',trigger)

    ]
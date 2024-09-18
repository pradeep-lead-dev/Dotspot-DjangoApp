from django.urls import path
from .views import *
# import views

urlpatterns = [
    path('/<str:collectionName>', getAll , name="getall") , 
    path('/<str:collectionName>/<str:objId>', specificAction , name="specific") ,
   
    ]
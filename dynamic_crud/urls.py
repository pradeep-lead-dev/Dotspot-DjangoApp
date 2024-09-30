from django.urls import path
from .views import *
# import views

urlpatterns = [
    path('/form', dummy , name="dummy") ,
   path('/get-all-tables',get_all_collections),
    path('/<str:collectionName>', getAll , name="getall") , 
    path('/<str:collectionName>/<str:param>', specificAction , name="specific") , 
    ]
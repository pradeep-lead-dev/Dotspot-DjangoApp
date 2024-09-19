from django.urls import path
from .views import *
# import views

urlpatterns = [
    path('/login', login , name="login"),
    # path('/check', check , name="check"),
    path('/register', register , name="register"),
    path('/me', verify_token_route , name="verify"),
    path('/protected', protected_route , name="protected"),
   
    
    ]
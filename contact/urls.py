# contact/urls.py
from django.urls import path
from . import views

app_name = 'contact'

urlpatterns = [
    path('submit/', views.contact_us, name='contact-us'),
]
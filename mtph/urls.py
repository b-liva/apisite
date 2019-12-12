from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('get-droplets', views.get_droplets, name='get_droplets'),
]

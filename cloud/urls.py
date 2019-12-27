from django.urls import path
from . import views
import digitalocean

urlpatterns = [
    path('', views.index, name='index'),
    # path('get-droplets', views.get_droplets, name='get_droplets'),
    # path('get-droplet-by-id', views.get_droplet_by_id, name='get_droplet_by_id'),
    path('test-json', views.test_json_response, name='test_json'),
    path('get-all-servers', views.get_all_servers, name='get_all_servers'),
    path('change-server', views.change_server, name='change_server'),
]

from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
import digitalocean


# Create your views here.
def index(request):
    return HttpResponse('hello basir')


def get_droplets(request):
    print('here.')
    token = '30481e4713012f917ea4f36b95a5528da83493b396e44142336d992aa6e5bc8a'
    manager = digitalocean.Manager(token=token)
    my_droplets = manager.get_all_droplets()
    ips = [droplet.ip_address for droplet in my_droplets]
    context = {
        'droplets': ips,
    }
    return JsonResponse(context, safe=False)

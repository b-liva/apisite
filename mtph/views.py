import json
import random
import time

from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
import digitalocean

# Create your views here.
from django.views.decorators.csrf import csrf_exempt
token = '30481e4713012f917ea4f36b95a5528da83493b396e44142336d992aa6e5bc8a'
manager = digitalocean.Manager(token=token)


class DoHandler(digitalocean.Manager):

    def __init__(self, token_key):
        self.token = token_key
        digitalocean.Manager.__init__(self, token=self.token)

    def get_sizes(self):
        sizes = self.get_data('sizes')
        avail_sizes = []
        for size in sizes['sizes']:
            if 's-' in size['slug'] and size['available']:
                avail_sizes.append(size)
        max_size = avail_sizes[len(avail_sizes) - 1]['slug']
        avail_regs = avail_sizes[len(avail_sizes) - 1]['regions']
        return max_size, avail_regs

    def get_droplets(self):
        my_droplets = self.get_all_droplets()
        droplets = [{
            'id': droplet.id,
            'ip': droplet.ip_address,
        } for droplet in my_droplets]

        return droplets

    def get_droplet_by_id(self, id):
        drop = self.get_droplet(id)
        print('ip: ', drop.ip_address)
        # print('data: ', data)

        return drop

    def create_new_droplet(self):
        avail_regs = ['ams3', 'fra1', 'lon1', 'nyc3', 'sfo1']
        max_size, avail_regs_raw = self.get_sizes()
        my_images = self.get_my_images()
        image_id = my_images[0].id
        region = random.choice(avail_regs)
        print(region)
        while region not in avail_regs_raw:
            region = random.choice(avail_regs)
            print(region)
        obj = digitalocean.Droplet(token=self.token, name='auto-generated', region=region, size=max_size,
                                   image=image_id)
        obj.create()
        print('Creating new droplet!')
        time.sleep(30)

        return obj

    def sandbox(self):
        # Taking a snapshot
        my_images = self.get_my_images()
        drop = self.get_all_droplets()[0]
        if len(my_images) == 0:
            print('no image')
            drop.take_snapshot('sm-01')


def index(request):
    return HttpResponse('hello basir')


def test_json_response(request):
    context = {
        'response': 'hello from a test method'
    }
    return JsonResponse(context, safe=False)


@csrf_exempt
def get_all_servers(request):
    do_handler = DoHandler(token)
    droplets = do_handler.get_droplets()
    print(droplets)
    return JsonResponse(droplets, safe=False)


@csrf_exempt
def change_server(request):
    data = json.loads(request.body.decode('utf-8'))
    id = data['id']
    print('fingind by id: ', id)
    do_handler = DoHandler(token)
    old_droplet = do_handler.get_droplet_by_id(id)
    # old_droplet.destroy()
    print('destroying old droplet! => ', old_droplet.ip_address)
    time.sleep(15)
    new_drop = do_handler.create_new_droplet()
    context = {
        'id': new_drop.id,
        'ip': new_drop.ip_address,
    }
    return JsonResponse(context, safe=False)



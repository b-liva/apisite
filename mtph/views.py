import datetime
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
            'tags': droplet.tags,
            'ip': droplet.ip_address,
        } for droplet in my_droplets if 'api' not in droplet.tags]

        return droplets

    def get_droplet_by_id(self, id):
        drop = self.get_droplet(id)
        print('ip: ', drop.ip_address)
        # print('data: ', data)

        return drop

    def create_new_droplet(self):
        avail_regs = ['ams3', 'fra1', 'lon1', 'nyc1', 'nyc3', 'tor1', 'sfo2']
        max_size, avail_regs_raw = self.get_sizes()
        my_images = self.get_my_images()
        image = my_images[-1]

        for a in my_images:
            if a.name == 'mtpserver16g':
                image = a

        region = random.choice(avail_regs)
        print('first reg: ', region)
        while region not in avail_regs_raw:
            region = random.choice(avail_regs)
            print('loop reg: ', region)

                                   image=image_id)
        creation_time = datetime.datetime.now()
        time_string = \
            str(creation_time.year) + \
            str(creation_time.month) + \
            str(creation_time.day) + '-' + \
            str(creation_time.hour) + \
            str(creation_time.minute) + \
            str(creation_time.second)
        obj = digitalocean.Droplet(token=self.token, name='ag-' + time_string, region=region, size=max_size,
                                   image=image.id)
        print('start creating.')
        obj.create()
        print('new droplet!', obj.ip_address)
        # except:
        #     self.create_new_droplet()
        print('start waiting')
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
    old_ip = old_droplet.ip_address
    print('destroying old droplet! => ', old_ip)
    old_droplet.destroy()
    time.sleep(20)
    new_drop = do_handler.create_new_droplet()
    new_drop = do_handler.get_droplet_by_id(new_drop.id)
    print('new drop created...: ', new_drop.ip_address)
    context = {
        'id': new_drop.id,
        'ip': new_drop.ip_address,
    }
    print(context)


    return JsonResponse(context, safe=False)

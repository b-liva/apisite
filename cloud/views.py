import os
import datetime
import json
import random
import time

import boto3
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
import digitalocean
from cloud.models import Server, Cloud
# Create your views here.
from django.views.decorators.csrf import csrf_exempt
token = os.environ['DO_TOKEN']
manager = digitalocean.Manager(token=token)

aws_access_key_id = os.environ['AWS_ACCESS_KEY_ID']
aws_secret_access_key = os.environ['AWS_SECRET_ACCESS_KEY']
ZONE_ID = os.environ['ZONE_ID']


class DoHandler(digitalocean.Manager):

    def __init__(self, token):
        self.token = token
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

    def create_new_droplet(self, server_type, old_ip):
        avail_regs = ['ams3', 'fra1', 'lon1', 'nyc1', 'nyc3', 'tor1', 'sfo2']
        max_size, avail_regs_raw = self.get_sizes()
        my_images = self.get_my_images()
        image = my_images[-1]

        print(image.name)
        image_name = f'mtpserver16g-{server_type}'

        for a in my_images:
            # if a.name == 'mtpserver16g':
            if a.name == image_name:
                image = a

        region = random.choice(avail_regs)
        print('first reg: ', region)
        while region not in avail_regs_raw:
            region = random.choice(avail_regs)
            print('loop reg: ', region)

        # try:
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
        obj.tags.append(str(old_ip).replace('.', '_'))
        print('start creating.')
        obj.create()
        print('new droplet!', obj.ip_address)
        # except:
        #     self.create_new_droplet()
        print('start waiting')

        time.sleep(30)

        return obj

    def determine_server_type(self, drop):
        snapshot_ids = drop.get_snapshots()
        proxy_snapshot_selector = 'pr01'
        if snapshot_ids:
            snap = snapshot_ids[len(snapshot_ids) - 1]
            snapshot_obj = self.get_snapshot(snap.id)
            proxy_snapshot_selector = snapshot_obj.name.split('-')[1]
        return proxy_snapshot_selector

    def create_drops(self, drops, cloud):
        for drop in drops:
            if not Server.objects.filter(server_id=drop['id'], ipv4=drop['ip']).exists():
                Server.objects.create(
                    cloud=cloud,
                    server_id=drop['id'],
                    ipv4=drop['ip'],
                    type=self.determine_server_type(self.get_droplet(drop['id'])),
                )

    def sandbox(self):
        # Taking a snapshot
        my_images = self.get_my_images()
        drop = self.get_all_droplets()[0]
        if len(my_images) == 0:
            print('no image')
            drop.take_snapshot('sm-01')


class AwsHandler:
    zone_id = ''

    def __init__(self, region_name=None):
        self.zone_id = ZONE_ID
        session = boto3.Session(
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )
        self.client = session.client("route53")

    def change_dns_ip(self, old_ip, new_ip):
        record_sets = self.client.list_resource_record_sets(
            HostedZoneId=self.zone_id,
        )

        for record in record_sets['ResourceRecordSets']:
            dns_value = {'Value': str(old_ip)}
            if record['Type'] == 'A' and dns_value in record['ResourceRecords']:

                new_dns = {'Value': str(new_ip)}
                record['ResourceRecords'].remove(dns_value)
                record['ResourceRecords'].append(new_dns)
                # record['ResourceRecords'] = [new_dns]
                self.client.change_resource_record_sets(
                    HostedZoneId=self.zone_id,
                    ChangeBatch={
                        'Comment': 'Good for now',
                        'Changes': [
                            {
                                'Action': 'UPSERT',
                                'ResourceRecordSet': record
                            }
                        ]
                    }
                )

    def random_ip(self):
        new_ip = str(int(200 * random.random())) \
                 + '.' + str(int(200 * random.random())) \
                 + '.' + str(int(200 * random.random())) \
                 + '.' + str(int(200 * random.random()))
        return new_ip


def index(request):
    return HttpResponse('hello basir')


def test_json_response(request):
    context = {
        'response': 'hello from a test method'
    }
    return JsonResponse(context, safe=False)


@csrf_exempt
def get_all_servers(request):
    droplets = list()
    for account in Cloud.objects.filter(is_active=True, owner__is_active=True):
        do_handler = DoHandler(account.secret)
        account_droplets = do_handler.get_droplets()
        do_handler.create_drops(account_droplets, account)
        droplets += account_droplets
    print(droplets)
    return JsonResponse(droplets, safe=False)


@csrf_exempt
def change_server(request):
    data = json.loads(request.body.decode('utf-8'))
    id = data['id']
    print('fingind by id: ', id)

    server = Server.objects.get(server_id=id)

    do_handler = DoHandler(server.cloud.secret)
    old_droplet = do_handler.get_droplet_by_id(id)
    old_ip = old_droplet.ip_address
    print('destroying old droplet! => ', old_ip)
    old_droplet.destroy()
    server.fail = True
    server.save()

    time.sleep(20)

    new_drop = do_handler.create_new_droplet(server.type, old_ip)
    new_drop = do_handler.get_droplet_by_id(new_drop.id)

    Server.objects.create(
        cloud=Cloud.objects.get(secret=do_handler.token),
        name=new_drop.name,
        server_id=new_drop.id,
        ipv4=new_drop.ip_address,
        type=do_handler.determine_server_type(new_drop),
    )
    print('new drop created...: ', new_drop.ip_address)
    context = {
        'id': new_drop.id,
        'ip': new_drop.ip_address,
    }
    print(context)

    return JsonResponse(context, safe=False)


@csrf_exempt
def change_dns(request):
    data = json.loads(request.body.decode('utf-8'))
    old_ip = data['old_ip']
    new_ip = data['new_ip']
    # todo: change dns
    aws_handler = AwsHandler()

    print(old_ip, 'is changing to: ', new_ip)
    aws_handler.change_dns_ip(old_ip, new_ip)

    # temp_old_ip = '46.101.163.133'
    # aws_handler.change_dns_ip(temp_old_ip, new_drop.ip_address)
    # wait to set new dns.


@csrf_exempt
def find_new_drop(request):
    data = json.loads(request.body.decode('utf-8'))
    old_ip = data['old_ip']
    server = Server.objects.get(server_id=id)
    do_handler = DoHandler(server.cloud.secret)
    drops = do_handler.get_all_droplets()
    for drop in drops:
        if old_ip.replace('.', '_') in drop.tags:
            return {
                'id': drop.id,
                'tags': drop.tags,
                'ip': drop.ip_address,
            }
    return False


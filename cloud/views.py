import os
import datetime
import json
import random
import time

import boto3
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
import digitalocean
from cloud.models import Server, Cloud, Status, SnapShot, Domain
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

    def create_new_droplet(self, snapshot_name, old_ip):
        avail_regs = ['ams3', 'fra1', 'lon1', 'nyc1', 'nyc3', 'tor1', 'sfo2']
        max_size, avail_regs_raw = self.get_sizes()
        my_images = self.get_my_images()

        image_name = snapshot_name

        for a in my_images:
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
                droplet = self.get_droplet_by_id(drop['id'])
                snapshot_name = droplet.image['name']
                snapshot = SnapShot.objects.get(name=snapshot_name)
                distinct_zone_ids = Domain.objects.values('zone_id').distinct()
                for zone_id in distinct_zone_ids:
                    aws_handler = AwsHandler(zone_id=zone_id['zone_id'])
                    dns = aws_handler.get_dns_by_ip(drop['ip'])
                    if dns:
                        break
                # todo: every proxy is attached to a User account and every server has a snapshot which is belonged to a server,
                # so we don't need to find the image and then the snapshot.
                Server.objects.create(
                    cloud=cloud,
                    server_id=drop['id'],
                    ipv4=drop['ip'],
                    status=Status.objects.get(title='clean'),
                    snapshot=snapshot,
                    dns=dns
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

    def __init__(self, region_name=None, zone_id=ZONE_ID):
        self.zone_id = zone_id
        session = boto3.Session(
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )
        self.client = session.client("route53")

    def change_dns_ip(self, old_ip, new_ip):
        # todo: deprecated.
        serve = Server.objects.get(ipv4=old_ip)
        zone_id = get_zone_id_by_subdomain(serve.dns)
        record_sets = self.client.list_resource_record_sets(
            HostedZoneId=zone_id,
        )

        for record in record_sets['ResourceRecordSets']:
            dns_value = {'Value': str(old_ip)}
            if record['Type'] == 'A' and dns_value in record['ResourceRecords']:

                new_dns = {'Value': str(new_ip)}
                record['ResourceRecords'].remove(dns_value)
                record['ResourceRecords'].append(new_dns)
                # record['ResourceRecords'] = [new_dns]
                self.client.change_resource_record_sets(
                    HostedZoneId=zone_id,
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

    def modify_dns(self, action, **kwargs):
        print('change dns kwargs: ', kwargs)
        print(self.zone_id)
        old_ip = new_ip = dns_name = ''
        if 'old_ip' in kwargs:
            old_ip = kwargs['old_ip']
            if old_ip != '':
                server = Server.objects.get(ipv4=old_ip)
                dns_name = server.dns
        if 'new_ip' in kwargs:
            new_ip = kwargs['new_ip']
        if 'dns_name' in kwargs:
            dns_name = kwargs['dns_name']
        print('**: ', dns_name)

        # zone_id = get_zone_id_by_subdomain(dns_name)
        """removes ip from dns if it exists and adds if not exists in dns."""
        record_sets = self.client.list_resource_record_sets(
            HostedZoneId=self.zone_id,
        )
        updatable_record = ''
        for record in record_sets['ResourceRecordSets']:
            if record['Type'] == 'A':
                if action == 'remove' and old_ip != '':
                    old_dns = {'Value': str(old_ip)}
                    if old_dns in record['ResourceRecords']:
                        record['ResourceRecords'].remove(old_dns)
                        updatable_record = record
                        break
                elif action == 'add' and new_ip != '' and record['Name'] == dns_name:
                    new_dns = {'Value': str(new_ip)}
                    record['ResourceRecords'].append(new_dns)
                    updatable_record = record
                    break
                elif action == 'swap' and old_ip != '' and new_ip != '':
                    old_dns = {'Value': str(old_ip)}
                    record['ResourceRecords'].remove(old_dns)
                    new_dns = {'Value': str(new_ip)}
                    record['ResourceRecords'].append(new_dns)
                    updatable_record = record
                    break

        if updatable_record != '':
            self.client.change_resource_record_sets(
                HostedZoneId=self.zone_id,
                ChangeBatch={
                    'Comment': 'Good for now',
                    'Changes': [
                        {
                            'Action': 'UPSERT',
                            'ResourceRecordSet': updatable_record
                        }
                    ]
                }
            )

    def get_dns_by_ip(self, ip):

        dns_value = {'Value': str(ip)}
        print(dns_value)
        record_sets = self.client.list_resource_record_sets(
            HostedZoneId=self.zone_id,
        )
        print('recordset', record_sets['ResourceRecordSets'])

        for record in record_sets['ResourceRecordSets']:
            print('record: ', record)
            if record['Type'] == 'A' and dns_value in record['ResourceRecords']:
                return record['Name']
        return 'addr.threeo.ml.'

    def all_dnses(self):
        # todo: for all zone_ids should be done.
        record_sets = self.client.list_resource_record_sets(
            HostedZoneId=self.zone_id,
        )

        for record in record_sets['ResourceRecordSets']:
            if record['Type'] == 'A' and record['Name'] == 'addr.threeo.ml.':
                return record['ResourceRecords']
        return False

    def random_ip(self):
        new_ip = str(int(200 * random.random())) \
                 + '.' + str(int(200 * random.random())) \
                 + '.' + str(int(200 * random.random())) \
                 + '.' + str(int(200 * random.random()))
        return new_ip


def index(request):
    return HttpResponse('hello basir')


def get_zone_id_by_subdomain(subdomain):
    subdomain_parts = subdomain.split('.')
    domain = f'{subdomain_parts[-3]}.{subdomain_parts[-2]}.'
    domain_obj = Domain.objects.get(domain=domain)
    return domain_obj.zone_id


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
    # todo: find a clean ip

    # todo option X01: change dns of related subdomains to this clean ip

    server = Server.objects.get(server_id=id)

    do_handler = DoHandler(server.cloud.secret)
    old_droplet = do_handler.get_droplet_by_id(id)
    old_ip = old_droplet.ip_address
    zone_id = get_zone_id_by_subdomain(server.dns)
    aws_handler = AwsHandler(zone_id=zone_id)
    old_dns_name = server.dns
    print('oldIp: ', old_ip)
    print('old_dns_name: ', old_dns_name)
    print('destroying old droplet! => ', old_ip)
    old_droplet.destroy()
    server.fail = True
    server.status = Status.objects.get(key='fail')
    server.save()

    time.sleep(20)

    # new_drop = do_handler.create_new_droplet(server.type, old_ip)
    new_drop = do_handler.create_new_droplet(server.snapshot.name, old_ip)
    new_drop = do_handler.get_droplet_by_id(new_drop.id)
    # todo: set status to testing for this server
    # todo: set dns here.
    Server.objects.create(
        cloud=Cloud.objects.get(secret=do_handler.token),
        name=new_drop.name,
        server_id=new_drop.id,
        ipv4=new_drop.ip_address,
        status=Status.objects.get(key='testing'),
        dns=old_dns_name,
        snapshot=server.snapshot
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
    old_ip = new_ip = dns_name = ''
    action = 'remove'
    ips = dict()
    if 'old_ip' in data:
        old_ip = data['old_ip']
        server = Server.objects.get(ipv4=old_ip)
        dns_name = server.dns
    if 'new_ip' in data:
        new_ip = data['new_ip']
        server = Server.objects.get(ipv4=new_ip)
        dns_name = server.dns
    if 'action' in data:
        action = data['action']
    if 'dns_name' in data:
        dns_name = data['dns_name']
    # change dns
    print('dns_name: ', dns_name)
    print('action: ', action)
    aws_handler = AwsHandler(zone_id=get_zone_id_by_subdomain(dns_name))
    print('zoneID: ', aws_handler.zone_id)
    try:
        aws_handler.modify_dns(action, old_ip=old_ip, new_ip=new_ip, dns_name=dns_name)
        status = True
    except:
        status = False
    context = {'status': status}
    return JsonResponse(context, safe=False)

    # temp_old_ip = '46.101.163.133'
    # aws_handler.change_dns_ip(temp_old_ip, new_drop.ip_address)
    # wait to set new dns.


@csrf_exempt
def find_new_drop(request):
    data = json.loads(request.body.decode('utf-8'))
    old_ip = data['old_ip']
    server = Server.objects.get(ipv4=old_ip)
    old_ip = old_ip.replace('.', '_')

    do_handler = DoHandler(server.cloud.secret)
    drops = do_handler.get_all_droplets()
    for drop in drops:
        if old_ip in drop.tags:
            context = ({
                'id': drop.id,
                'tags': drop.tags,
                'ip': drop.ip_address,
            })
            return JsonResponse(context, safe=False)
    return False


@csrf_exempt
def get_all_dnses(request):
    aws_handler = AwsHandler()
    all_dnses = aws_handler.all_dnses()
    print(all_dnses)
    context = {
        'dnses': all_dnses
    }
    return JsonResponse(context, safe=False)

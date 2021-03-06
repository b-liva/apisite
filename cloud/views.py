import os
import datetime
import json
import random
import time
import logging
import boto3
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
import digitalocean
from cloud.models import Server, Cloud, Status, SnapShot, Domain
from django.views.decorators.csrf import csrf_exempt
# Create your views here.
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')

file_handler = logging.FileHandler('cloud.log')
# file_handler.setLevel(logging.ERROR)
file_handler.setFormatter(formatter)

# stream_handler = logging.StreamHandler()
# stream_handler.setFormatter(formatter)

logger.addHandler(file_handler)
# logger.addHandler(stream_handler)

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
        while drop.ip_address is None:
            logger.warning(f'droplet {id} has not an ip address: ', drop.ip_address is None)
            print(f'droplet {id} has not an ip address: ', drop.ip_address is None)
            print(f'waiting to find ip address of {id}')
            time.sleep(10)
            drop = self.get_droplet(id)
            print(f'droplet {id} has not an ip address: ', drop.ip_address is None, drop.ip_address)
        print('ip: ', drop.ip_address)
        # print('data: ', data)

        return drop

    def create_new_droplet(self, snapshot_name, old_ip):
        avail_regs = ['ams3', 'fra1', 'lon1', 'nyc1', 'nyc3', 'tor1', 'sfo2']
        # avail_regs = ['ams3', 'fra1', 'nyc1', 'nyc3', 'tor1', 'sfo2']
        max_size, avail_regs_raw = self.get_sizes()
        my_images = self.get_my_images()

        image_name = snapshot_name

        for a in my_images:
            if a.name == image_name:
                image = a

        region = random.choice(avail_regs)
        while region not in avail_regs_raw:
            region = random.choice(avail_regs)

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
        # find number of droplets to wait if needed.
        ds = self.get_all_droplets()
        droplets_count = len(ds)
        while droplets_count >= 10:
            logger.warning('no more room to create droplet')
            print('no more room to create droplet')
            time.sleep(15)
            ds = self.get_all_droplets()
            droplets_count = len(ds)
        try:
            obj.create()
        except:
            logger.exception(f'New droplet creation failed to replace {old_ip}')
        # except:
        #     self.create_new_droplet()
        time.sleep(30)
        return obj

    def create_drops(self, drops, cloud):
        for drop in drops:
            if not Server.objects.filter(server_id=drop['id'], ipv4=drop['ip']).exists():
                droplet = self.get_droplet_by_id(drop['id'])
                snapshot_name = droplet.image['name']
                # todo (01): If there is not such a snapshot it should be created here.
                snapshot = SnapShot.objects.get(name=snapshot_name)
                distinct_zone_ids = Domain.objects.values('zone_id').distinct()
                for zone_id in distinct_zone_ids:
                    aws_handler = AwsHandler(zone_id=zone_id['zone_id'])
                    # todo (02): what if we haven't added the ip to a dns before?
                    dns = aws_handler.get_dns_by_ip(drop['ip'])
                    if dns:
                        break

                try:
                    Server.objects.create(
                        cloud=cloud,
                        server_id=drop['id'],
                        ipv4=drop['ip'],
                        status=Status.objects.get(title='clean'),
                        snapshot=snapshot,
                        dns=dns
                    )
                except:
                    logger.exception('Server object creation failed.')


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
        serve = Server.objects.filter(ipv4=old_ip).last()
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
                try:
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
                except:
                    logger.exception(f'changing dns failed.old ip: {old_ip}, new ip: {new_ip}, zone id: {zone_id}')

    def modify_dns(self, action, **kwargs):
        print('change dns kwargs: ', kwargs)
        print(self.zone_id)
        old_ip = new_ip = dns_name = ''
        if 'old_ip' in kwargs:
            old_ip = kwargs['old_ip']
            if old_ip != '':
                server = Server.objects.filter(ipv4=old_ip).last()
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
            try:
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
            except:
                logger.exception(f'failed to change dns. action: {action}')

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
        logger.warning(f'No dns found for {ip} in {self.zone_id}')
        return False

    def all_dnses(self):
        # todo: for all zone_ids should be done.
        record_sets = self.client.list_resource_record_sets(
            HostedZoneId=self.zone_id,
        )

        for record in record_sets['ResourceRecordSets']:
            if record['Type'] == 'A':
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
    try:
        domain_obj = Domain.objects.get(domain=domain)
    except:
        logger.exception('No Domain obj found')
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

    return JsonResponse(droplets, safe=False)


@csrf_exempt
def change_server(request):
    data = json.loads(request.body.decode('utf-8'))
    id = data['id']
    logger.info(f'fingind server by id: {id}')
    # todo: find a clean ip

    # todo option X01: change dns of related subdomains to this clean ip
    try:
        server = Server.objects.filter(server_id=id).last()
    except:
        logger.exception(f'No server found for {id}')

    do_handler = DoHandler(server.cloud.secret)
    old_droplet = do_handler.get_droplet_by_id(id)
    old_ip = old_droplet.ip_address
    zone_id = get_zone_id_by_subdomain(server.dns)
    aws_handler = AwsHandler(zone_id=zone_id)
    old_dns_name = server.dns
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
    try:
        Server.objects.create(
            cloud=Cloud.objects.get(secret=do_handler.token),
            name=new_drop.name,
            server_id=new_drop.id,
            ipv4=new_drop.ip_address,
            status=Status.objects.get(key='testing'),
            dns=old_dns_name,
            snapshot=server.snapshot
        )
    except:
        logger.exception(f"Server Creation faild. but {old_ip} was destroyed.")
    print('new drop created...: ', new_drop.ip_address)
    context = {
        'id': new_drop.id,
        'ip': new_drop.ip_address,
    }
    print(context)

    return JsonResponse(context, safe=False)


@csrf_exempt
def change_dns(request):
    # todo (4): If this is the last dns and it is being removed. save and in the next loop delete it.
    # todo (7): what if it is a duplicate ip.
    data = json.loads(request.body.decode('utf-8'))
    old_ip = new_ip = dns_name = ''
    action = 'remove'
    ips = dict()
    if 'old_ip' in data:
        old_ip = data['old_ip']
        server = Server.objects.filter(ipv4=old_ip).last()
        dns_name = server.dns
    if 'new_ip' in data:
        new_ip = data['new_ip']
        server = Server.objects.filter(ipv4=new_ip).last()
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
        logger.exception(f"modifying dns failed. action: {action}")
    context = {'status': status}
    return JsonResponse(context, safe=False)

    # temp_old_ip = '46.101.163.133'
    # aws_handler.change_dns_ip(temp_old_ip, new_drop.ip_address)
    # wait to set new dns.


@csrf_exempt
def find_new_drop(request):
    data = json.loads(request.body.decode('utf-8'))
    old_ip = data['old_ip']
    logger.info(f'find_new_drop => {old_ip}')
    server = Server.objects.filter(ipv4=old_ip).last()
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
    context = {
        'status': False
    }
    return JsonResponse(context, safe=False)


@csrf_exempt
def get_all_ips(request):
    drops = []
    for account in Cloud.objects.filter(is_active=True, owner__is_active=True):
        print(account)
        do_handler = DoHandler(account.secret)
        drops.extend(do_handler.get_all_droplets())
    print(len(drops))
    ips = [droplet.ip_address for droplet in drops if 'api' not in droplet.tags]
    for ip in ips:
        print(ip)
    return JsonResponse(ips, safe=False)
    

@csrf_exempt
def get_all_dnses(request):
    data = json.loads(request.body.decode('utf-8'))
    zone_id = data['zone_id']

    aws_handler = AwsHandler(zone_id=zone_id)
    all_dnses = aws_handler.all_dnses()
    print(all_dnses)
    context = {
        'dnses': all_dnses
    }
    return JsonResponse(context, safe=False)

from django.shortcuts import render
from django.http import HttpResponse, JsonResponse


# Create your views here.
def index(request):
	return HttpResponse('hello basir')


def get_droplets(request):
	print('here.')
	token = '30481e4713012f917ea4f36b95a5528da83493b396e44142336d992aa6e5bc8a'

	return JsonResponse('hello basirkhan', safe=False)
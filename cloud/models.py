from django.db import models
from django.contrib.auth import get_user_model
# Create your models here.
from common.models import TimeStampedModel

User = get_user_model()


class Type(TimeStampedModel):
    name = models.CharField(max_length=20)


class Cloud(TimeStampedModel):
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    secret = models.CharField(max_length=100)
    access = models.CharField(max_length=100)
    type = models.ForeignKey(Type, on_delete=models.CASCADE)


class Server(TimeStampedModel):
    cloud = models.ForeignKey(Cloud, on_delete=models.CASCADE)
    name = models.CharField(max_length=30)
    ipv4 = models.CharField(max_length=20)
    dns = models.CharField(max_length=200, blank=True, null=True)
    fail = models.BooleanField(default=False)

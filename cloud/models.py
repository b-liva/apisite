from django.db import models
from django.contrib.auth import get_user_model
# Create your models here.
from common.models import TimeStampedModel

User = get_user_model()


class Type(TimeStampedModel):
    name = models.CharField(max_length=20)

    def save(self, force_insert=False, force_update=False, using=None,
             update_fields=None):
        self.name = self.name.replace(' ', '_')
        super().save()

    def __str__(self):
        return '%s ' % self.name


class Cloud(TimeStampedModel):
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    secret = models.CharField(max_length=100)
    access = models.CharField(max_length=100, blank=True, null=True)
    type = models.ForeignKey(Type, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=False)

    def __str__(self):
        return '%s: %s owned by: %s' % (self.type.name.capitalize(), self.name.capitalize(), self.owner.username.capitalize())


class Status(models.Model):
    key = models.CharField(max_length=15)
    title = models.CharField(max_length=20)

    def __str__(self):
        return '%s: %s' % (self.key, self.title)


class Proxy(TimeStampedModel):
    name = models.CharField(max_length=25)
    url_port = models.CharField(max_length=100)

    def __str__(self):
        return '%s' % self.name


class SnapShot(TimeStampedModel):
    name = models.CharField(max_length=25)
    proxy = models.OneToOneField(Proxy, on_delete=models.CASCADE, primary_key=True)

    def __str__(self):
        return '%s - %s' % (self.name, self.proxy)


class Server(TimeStampedModel):
    cloud = models.ForeignKey(Cloud, on_delete=models.CASCADE)
    status = models.ForeignKey(Status, on_delete=models.DO_NOTHING)
    name = models.CharField(max_length=30, blank=True, null=True)
    server_id = models.CharField(max_length=30)
    ipv4 = models.CharField(max_length=20)
    dns = models.CharField(max_length=200, blank=True, null=True)
    fail = models.BooleanField(default=False)
    type = models.CharField(max_length=10, default='front')
    proxy = models.ForeignKey(Proxy, on_delete=models.DO_NOTHING)

    def __str__(self):
        return '%s - %s - %s - %s -  %s - %s' % (self.cloud.owner.username.capitalize(), self.cloud.name.capitalize(), self.cloud.type.name.capitalize(), self.server_id, self.ipv4, self.type)

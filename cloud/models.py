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

    def __str__(self):
        return '%s: %s owned by: %s' % (self.type.name.capitalize(), self.name.capitalize(), self.owner.username.capitalize())


class Server(TimeStampedModel):
    cloud = models.ForeignKey(Cloud, on_delete=models.CASCADE)
    name = models.CharField(max_length=30, blank=True, null=True)
    ipv4 = models.CharField(max_length=20)
    dns = models.CharField(max_length=200, blank=True, null=True)
    fail = models.BooleanField(default=False)

    def __str__(self):
        return 'IP: %s - %s - %s' % (self.ipv4, self.cloud.type.name.capitalize(), self.cloud.owner.username.capitalize())



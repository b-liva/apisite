from django.contrib import admin
from .models import (
    Cloud,
    Server,
    Type,
    Status,
    Proxy,
    SnapShot,
    Domain
)

# Register your models here.
admin.site.register(Cloud)
admin.site.register(Server)
admin.site.register(Type)
admin.site.register(Status)
admin.site.register(Proxy)
admin.site.register(SnapShot)
admin.site.register(Domain)
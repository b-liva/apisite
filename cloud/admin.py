from django.contrib import admin
from .models import (
    Cloud,
    Server,
    Type
)

# Register your models here.
admin.site.register(Cloud)
admin.site.register(Server)
admin.site.register(Type)

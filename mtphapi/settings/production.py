from .base import *


ALLOWED_HOSTS = ['165.227.65.164']
SECRET_KEY = set_secret_key(
    os.environ['DJANGO_SETTINGS_MODULE'],
    'SECRET_KEY_PRODUCTION'
)
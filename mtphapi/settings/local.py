from .base import *

DEBUG = True

SECRET_KEY = set_secret_key(
    os.environ['DJANGO_SETTINGS_MODULE'],
    'SECRET_KEY_LOCAL'
)

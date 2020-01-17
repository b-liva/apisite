# Generated by Django 3.0 on 2020-01-16 14:20

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('cloud', '0009_server_proxy'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='server',
            name='proxy',
        ),
        migrations.RemoveField(
            model_name='server',
            name='type',
        ),
        migrations.AddField(
            model_name='proxy',
            name='owner',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='server',
            name='snapshot',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.DO_NOTHING, to='cloud.SnapShot'),
            preserve_default=False,
        ),
    ]
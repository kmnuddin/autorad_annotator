# Generated by Django 4.2.11 on 2024-09-26 09:27

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('AutoRad', '0012_alter_imgclass_imgfile'),
    ]

    operations = [
        migrations.AddField(
            model_name='imgclass',
            name='userID',
            field=models.OneToOneField(default='000000000000', on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
    ]

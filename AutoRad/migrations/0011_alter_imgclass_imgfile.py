# Generated by Django 4.2.11 on 2024-09-26 09:12

import AutoRad.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('AutoRad', '0010_remove_imgclass_patientid_remove_imgclass_reportid'),
    ]

    operations = [
        migrations.AlterField(
            model_name='imgclass',
            name='imgFile',
            field=models.ImageField(upload_to=AutoRad.models.userFolder),
        ),
    ]

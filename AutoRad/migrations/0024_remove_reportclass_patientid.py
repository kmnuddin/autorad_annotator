# Generated by Django 4.2.11 on 2024-09-26 10:16

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('AutoRad', '0023_rename_user_imgclass_useracc'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='reportclass',
            name='patientID',
        ),
    ]

# Generated by Django 4.2.11 on 2024-09-26 09:33

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('AutoRad', '0016_remove_imgclass_user'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='patientclass',
            name='userID',
        ),
    ]
# Generated by Django 4.2.11 on 2024-09-20 03:26

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('AutoRad', '0006_remove_imgclass_reportid_alter_imgclass_format_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='imgclass',
            name='created_at',
        ),
        migrations.RemoveField(
            model_name='imgclass',
            name='imgKey',
        ),
        migrations.RemoveField(
            model_name='imgclass',
            name='modified_at',
        ),
        migrations.RemoveField(
            model_name='imgclass',
            name='url',
        ),
    ]

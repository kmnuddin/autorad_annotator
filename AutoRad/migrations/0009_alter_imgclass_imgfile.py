# Generated by Django 4.2.11 on 2024-09-26 08:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('AutoRad', '0008_imgclass_created_at_imgclass_modified_at_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='imgclass',
            name='imgFile',
            field=models.ImageField(upload_to='.'),
        ),
    ]

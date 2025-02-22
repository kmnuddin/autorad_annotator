# Generated by Django 4.2.11 on 2024-08-29 21:48

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='imgClass',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('imgName', models.CharField(max_length=200)),
                ('imgFile', models.ImageField(upload_to='.\\media')),
                ('docID', models.IntegerField()),
                ('reportID', models.IntegerField()),
            ],
        ),
        migrations.CreateModel(
            name='maskClass',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('maskName', models.CharField(max_length=200)),
                ('maskType', models.CharField(max_length=200)),
                ('imageID', models.IntegerField()),
                ('maskFile', models.CharField(max_length=200)),
                ('maskProperty', models.CharField(max_length=200)),
            ],
        ),
        migrations.CreateModel(
            name='reprotClass',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reportName', models.CharField(max_length=200)),
                ('imgId', models.IntegerField()),
                ('reportContent', models.CharField(max_length=200)),
            ],
        ),
    ]

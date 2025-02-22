# Generated by Django 4.2.11 on 2024-10-05 15:58

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('AutoRad', '0030_alter_imgclass_useracc_alter_maskclass_imgid_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='maskclass',
            name='maskKey',
        ),
        migrations.AlterField(
            model_name='imgclass',
            name='imgName',
            field=models.CharField(default='example_image.png', help_text='The name of the uploaded image.', max_length=100),
        ),
        migrations.AlterField(
            model_name='imgclass',
            name='userAcc',
            field=models.ForeignKey(default='1', on_delete=django.db.models.deletion.SET_DEFAULT, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='maskclass',
            name='imgID',
            field=models.ForeignKey(default='1', on_delete=django.db.models.deletion.SET_DEFAULT, to='AutoRad.imgclass'),
        ),
        migrations.AlterField(
            model_name='maskclass',
            name='maskAngle',
            field=models.FloatField(default=0.0),
        ),
        migrations.AlterField(
            model_name='maskclass',
            name='maskFile',
            field=models.ImageField(upload_to='.'),
        ),
        migrations.AlterField(
            model_name='maskclass',
            name='maskName',
            field=models.CharField(default='example_mask.png', help_text='The name of the mask', max_length=200),
        ),
        migrations.AlterField(
            model_name='maskclass',
            name='maskType',
            field=models.CharField(default='Type1', help_text='The type of the mask, ', max_length=200),
        ),
        migrations.AlterField(
            model_name='testclass',
            name='userID',
            field=models.ForeignKey(default='1', on_delete=django.db.models.deletion.SET_DEFAULT, to=settings.AUTH_USER_MODEL),
        ),
    ]

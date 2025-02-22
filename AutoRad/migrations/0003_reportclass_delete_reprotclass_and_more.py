# Generated by Django 4.2.11 on 2024-09-10 15:41

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('AutoRad', '0002_patientclass_remove_imgclass_docid_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='reportClass',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reportName', models.CharField(max_length=200)),
                ('reprotID', models.CharField(default='000000000000', max_length=100)),
                ('reportContent', models.CharField(max_length=200)),
            ],
        ),
        migrations.DeleteModel(
            name='reprotClass',
        ),
        migrations.RemoveField(
            model_name='imgclass',
            name='patientID',
        ),
        migrations.AddField(
            model_name='imgclass',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='imgclass',
            name='modified_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name='imgclass',
            name='url',
            field=models.CharField(default='.\\media', max_length=100),
        ),
        migrations.AddField(
            model_name='maskclass',
            name='imgID',
            field=models.ForeignKey(default=0, on_delete=django.db.models.deletion.CASCADE, to='AutoRad.imgclass'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='patientclass',
            name='userID',
            field=models.OneToOneField(default=0, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='reportclass',
            name='patientID',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='AutoRad.patientclass'),
        ),
        migrations.AlterField(
            model_name='imgclass',
            name='reportID',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='AutoRad.reportclass'),
        ),
    ]

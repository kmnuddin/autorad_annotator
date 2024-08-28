from django.db import models

class img(models.Model):
    imgName = models.CharField(max_length=200)
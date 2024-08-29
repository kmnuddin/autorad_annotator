from django.db import models

class imgClass(models.Model):
    imgName = models.CharField(max_length=200)
    imgFile = models.ImageField(upload_to='.\media')
    docID = models.IntegerField()
    reportID = models.IntegerField()
    
class maskClass(models.Model):
    maskName = models.CharField(max_length=200)
    maskType = models.CharField(max_length=200)
    imageID = models.IntegerField()
    maskFile = models.CharField(max_length=200)
    maskProperty = models.CharField(max_length=200)
    
class reprotClass(models.Model):
    reportName = models.CharField(max_length=200)
    imgId = models.IntegerField()
    reportContent = models.CharField(max_length=200)
    
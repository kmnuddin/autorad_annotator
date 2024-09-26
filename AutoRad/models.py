from django.db import models
from django.contrib.auth.models import User
import os

### Each user will have multiple imgs:   user --[1 to many] --> img
### Each image will have multiple masks: img --[1 to many] --> mask
### Each image will have only one report: img --[1 to 1] --> img
def user_directory_path(instance, filename):
    print(instance.userAcc)
    return 'user_{0}/{1}'.format(instance.userAcc.id, filename)

def userFolder(instance, filename):
    return ""

class patientClass(models.Model):
    patientID = models.CharField(max_length=100,default="000000000000")
    patientName = models.CharField(max_length=100,default="")
    
    # userID = models.ForeignKey(User,on_delete=models.CASCADE,default="000000000000")
    
class reportClass(models.Model):
    reportName = models.CharField(max_length=200,default="")
    reprotID = models.CharField(max_length=100,default="000000000000")
    reportContent = models.CharField(max_length=200,default="")
    
    # patientID = models.ForeignKey(patientClass,on_delete=models.CASCADE,default="000000000000")
    
class imgClass(models.Model):
    # imgKey = models.CharField(max_length=100,help_text="The public ID of the upoloaded file.",default="000000000000")
    imgName = models.CharField(max_length=100,help_text="The name of the uploaded image.",default="")
    # url = models.CharField(max_length=100,default='./media')
    imgFile = models.ImageField(upload_to='.')
    # width = models.IntegerField(help_text="Width in px",default=320)
    # height = models.IntegerField(help_text="height in px",default=320)
    # format = models.CharField(max_length=10,default="image/png")
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    
    # userAcc = models.ForeignKey(User, on_delete=models.CASCADE,default="000000000000")
    
    # reportID = models.ForeignKey(reportClass,on_delete=models.CASCADE,default="000000000000")
    
class maskClass(models.Model):
    maskKey = models.CharField(max_length=100,help_text="The internal ID of the mask.",default="000000000000")
    maskName = models.CharField(max_length=200,help_text="The name of the mask",default="")
    maskType = models.CharField(max_length=200,help_text="The type of the mask, ",default="")
    maskFile = models.CharField(max_length=200,default="")
    maskPts = models.CharField(max_length=1000,default="[]")
    maskTop = models.IntegerField(default=0)
    maskLeft = models.IntegerField(default=0)
    maskAngle = models.IntegerField(default=0)
    maskScale = models.FloatField(default=1.0)
    maskOpacity = models.FloatField(default=1.0)
    maskCornerColor = models.CharField(max_length = 7, help_text = "The color code for corner",default="#0000ff")
    maskStrokeColor = models.CharField(max_length = 7, help_text = "The color code for line",default="#ff0000")
    
    imgID = models.ForeignKey(imgClass,on_delete=models.CASCADE,default="000000000000")
    

    

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
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
    patientID = models.CharField(max_length=100,default="1")
    patientName = models.CharField(max_length=100,default="")
    
    # userID = models.ForeignKey(User,on_delete=models.CASCADE,default="000000000000")
    
class reportClass(models.Model):
    reportName = models.CharField(max_length=200,default="")
    reprotID = models.CharField(max_length=100,default="1")
    reportContent = models.CharField(max_length=200,default="")
    
    # patientID = models.ForeignKey(patientClass,on_delete=models.CASCADE,default="000000000000")
    
    # reportID = models.ForeignKey(reportClass,on_delete=models.CASCADE,default="1")
    
class MRI(models.Model):
    filename = models.CharField(max_length=200, default="example_image.png")
    filetype = models.CharField(max_length=30, default="image/png")
    path = models.ImageField(upload_to='.')
    width = models.IntegerField(default=320)
    height = models.IntegerField(default=320)
    created_at = models.DateTimeField(auto_now_add=True)

    user = models.ForeignKey(User, on_delete=models.SET_DEFAULT, default="-1")


class UNetMask(models.Model):
    """
    Combine both the original UNet mask and
    the edited version in this same model.
    """
    MRI = models.ForeignKey(MRI, on_delete=models.SET_DEFAULT, default="-1")

    mask_img_filename = models.CharField(max_length=200, default="example_mask.png")
    mask_img_path = models.ImageField(upload_to='.', default="image/mask")
    mask_npy_filename = models.CharField(max_length=200, default="example_mask.npy")
    mask_npy_path = models.CharField(max_length=200, default='media/example_mask.npy')
    width = models.IntegerField(default=320)
    height = models.IntegerField(default=320)

    # e.g., "original", "edited" or "v1", "v2", etc.
    mask_version = models.CharField(max_length=20, default="original")

    # track if user has manually edited it
    edited = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)


class UNetMaskStructure(models.Model):
    """
    Store structures (e.g. “IVD”, “PE”) for *any* UNet mask,
    whether original or edited. All in one table.
    """
    unet_mask = models.ForeignKey(UNetMask, on_delete=models.SET_DEFAULT, default=-1)

    structure = models.CharField(max_length=50, default="")
    filename = models.CharField(max_length=200, default="")
    path = models.ImageField(upload_to='.', default="image/mask")
    width = models.IntegerField(default=320)
    height = models.IntegerField(default=320)

    created_at = models.DateTimeField(auto_now_add=True)



class testClass(models.Model):
    fn = models.CharField(max_length=10,default="John")
    ln = models.CharField(max_length=10,default="Doe")
    
    userID = models.ForeignKey(User,on_delete=models.SET_DEFAULT,default="1")
    

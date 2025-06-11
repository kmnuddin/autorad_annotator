from django.db import models

from django.conf import settings

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


class Patient(models.Model):
    id_from_inst = models.CharField(max_length=300, default="1", blank=True)

    # Patient's Age (e.g., "045Y")
    age = models.CharField(max_length=10, blank=True, null=True)

    # Patient's Weight in kilograms (e.g., 70.50)
    weight = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)

    # Patient's Height in meters (e.g., 1.75)
    height = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True)

    # Patient's Sex: M, F, or O (Other)
    SEX_CHOICES = (
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    )

    MODULES = (
        ('Segmentation', 'Segmentation'),
        ('Assessment/Reporting', 'Assessment/Reporting')
    )
    sex = models.CharField(max_length=1, choices=SEX_CHOICES, blank=True, null=True)

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_DEFAULT, default="-1")

    from_module = models.CharField(max_length=50, choices=MODULES, blank=True, null=True)

    annotator_inst = models.CharField(max_length=100, blank=True, null=True)
    def __str__(self):
        return self.id_from_inst

class MRI(models.Model):
    filename = models.CharField(max_length=200, default="example_image.png")
    filetype = models.CharField(max_length=30, default="image/png")
    path = models.ImageField(upload_to='.')
    width = models.IntegerField(default=320)
    height = models.IntegerField(default=320)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_DEFAULT, default="-1")

    modality = models.CharField(max_length=50, blank=True, null=True)
    manufacturer = models.CharField(max_length=100, blank=True, null=True)

    pixel_spacing = models.CharField(max_length=50, blank=True, null=True)
    protocol_name = models.CharField(max_length=100, blank=True, null=True)
    # New fields for MRI type and orientation:
    mri_type = models.CharField(max_length=20, blank=True, null=True)  # e.g., T1, T2, etc.
    orientation = models.CharField(max_length=20, blank=True, null=True)

    LUMBAR_LEVEL_CHOICES = [
        ('L1-L2', 'L1-L2'),
        ('L2-L3', 'L2-L3'),
        ('L3-L4', 'L3-L4'),
        ('L4-L5', 'L4-L5'),
        ('L5-S1', 'L5-S1'),
    ]
    lumbar_level = models.CharField(max_length=50, choices=LUMBAR_LEVEL_CHOICES, blank=True, null=True)

    Patient = models.ForeignKey(Patient, on_delete=models.SET_DEFAULT, default="-1", null=True, blank=True)

    repetition_time = models.CharField(max_length=20, blank=True, null=True)
    echo_time = models.CharField(max_length=20, blank=True, null=True)
    inversion_time = models.CharField(max_length=20, blank=True, null=True)
    flip_angle = models.CharField(max_length=20, blank=True, null=True)
    magnetic_field_strength = models.CharField(max_length=20, blank=True, null=True)
    acquisition_matrix = models.CharField(max_length=50, blank=True, null=True)
    pixel_bandwidth = models.CharField(max_length=20, blank=True, null=True)
    fov = models.CharField(max_length=50, blank=True, null=True)

    MODULES = (
        ('Segmentation', 'Segmentation'),
        ('Assessment/Reporting', 'Assessment/Reporting')
    )

    module = models.CharField(max_length=50, choices=MODULES, blank=True, null=True)
    annotator_inst = models.CharField(max_length=100, blank=True, null=True)


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
    edited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_DEFAULT, default="-1", blank=True, null=True)

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


class Assessment_Comments(models.Model):
    Patient = models.ForeignKey(Patient, on_delete=models.SET_DEFAULT, default="-1")
    MRI = models.ForeignKey(MRI, on_delete=models.SET_DEFAULT, default="-1")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_DEFAULT, default="-1")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # box coords, stored *normalized* 0.0–1.0, so you never have to worry about
    # different resolutions later
    x = models.FloatField(help_text="Left coordinate, normalized [0–1]")
    y = models.FloatField(help_text="Top coordinate, normalized [0–1]")
    width = models.FloatField(help_text="Width, normalized [0–1]")
    height = models.FloatField(help_text="Height, normalized [0–1]")

    comment = models.TextField(blank=True)
    tag = models.CharField(max_length=200, default="")
from django.core.files.storage import default_storage
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import MRI, UNetMask, UNetMaskStructure


@receiver(post_delete, sender=MRI)
def delete_mri_file(sender, instance, **kwargs):
    """
    Deletes the file associated with the MRI instance after it is deleted.
    """
    if instance.path:
        # Deletes the file from storage. save=False prevents saving the model.
        instance.path.delete(save=False)
        print(f"Deleted MRI file: {instance.path}")


@receiver(post_delete, sender=UNetMask)
def delete_unetmask_files(sender, instance, **kwargs):
    """
    Deletes the mask image and mask npy file for a UNetMask instance.
    """

    # 1) delete the PNG via its FileField:
    if instance.mask_img_path:
        instance.mask_img_path.delete(save=False)
        print(f"Deleted UNetMask image file: {instance.mask_img_path.name}")

    # 2) delete the .npy via the S3 storage backend
    npy_key = instance.mask_npy_path  # this is the S3 key you saved earlier
    if npy_key:
        if default_storage.exists(npy_key):
            default_storage.delete(npy_key)
            print(f"Deleted UNetMask npy file from storage: {npy_key}")


@receiver(post_delete, sender=UNetMaskStructure)
def delete_unetmaskstructure_file(sender, instance, **kwargs):
    """
    Deletes the file associated with the UNetMaskStructure instance after it is deleted.
    """
    if instance.path:
        instance.path.delete(save=False)
        print(f"Deleted UNetMaskStructure file: {instance.path}")

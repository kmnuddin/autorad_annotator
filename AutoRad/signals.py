import os
from django.conf import settings
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
    # Delete the mask image from storage.
    if instance.mask_img_path:
        instance.mask_img_path.delete(save=False)
        print(f"Deleted UNetMask image file: {instance.mask_img_path}")

    # For the mask_npy_path, which is a CharField storing a path,
    # we construct the full path and delete the file if it exists.
    mask_npy_path = instance.mask_npy_path
    if mask_npy_path:
        # If the stored path is relative (e.g. 'example_mask.npy' or 'media/example_mask.npy'),
        # construct the full path relative to MEDIA_ROOT.
        full_path = mask_npy_path
        if not os.path.isabs(full_path):
            full_path = os.path.join(settings.MEDIA_ROOT, mask_npy_path)
        if os.path.exists(full_path):
            os.remove(full_path)
            print(f"Deleted UNetMask npy file: {full_path}")


@receiver(post_delete, sender=UNetMaskStructure)
def delete_unetmaskstructure_file(sender, instance, **kwargs):
    """
    Deletes the file associated with the UNetMaskStructure instance after it is deleted.
    """
    if instance.path:
        instance.path.delete(save=False)
        print(f"Deleted UNetMaskStructure file: {instance.path}")

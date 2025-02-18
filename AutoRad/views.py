import numpy as np
from django.shortcuts import render, redirect
from django.core.files.storage import FileSystemStorage
from django.contrib.auth.forms import UserCreationForm
from django.views.generic.edit import CreateView
from django.core.files.base import ContentFile
from django.urls import reverse_lazy
from django.contrib.auth import login
from urllib.parse import unquote
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.http import JsonResponse
import cv2
import shutil
from PIL import Image
import torch
import pickle
from .utils import model, device
import matplotlib.pyplot as plt
from django.conf import settings
import io
import os
import logging
import json
import datetime
import base64
from django.contrib import messages
from django.http import HttpResponse

# import customized class models
from .models import patientClass, reportClass, MRI, UNetMask, UNetMaskStructure
from .utils import one_hot_encode_masks, dicom_to_png

from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt

SELECTED_MRI_ID = None

STRUCT_COLORS = {
    'IVD': 64,
    'PE': 128,
    'TS': 192,
    'AAP': 255
}


class SignUpView(CreateView):
    form_class = UserCreationForm
    template_name = 'registration/signup.html'
    success_url = reverse_lazy('home')  # Redirect to the home page after signup

    def form_valid(self, form):
        response = super().form_valid(form)
        user = form.save()
        print("User created:", user.username)
        login(self.request, user)  # Automatically log in the user after registration
        return response


@login_required
### When homepage is loading, it will pull all the image from DB.
def home(request):
    images = MRI.objects.all()
    context = {'images': images}
    return render(request, 'home.html', context)
    # return render(request, 'home.html')

def saveImg(request):
    return render(request, 'saveImg.html')
## This view is not in use....
# def upload_image(request):
#     context = {}
#     print("If you see this message, this function is under using!") ## testing
#     if request.method == 'POST' and request.FILES['image']:
#         image = request.FILES['image']
#         fs = FileSystemStorage()
#         filename = fs.save(image.name, image)
#         image_url = fs.url(filename)
#         context['image_url'] = image_url
#     return render(request, 'home.html', context)

logger = logging.getLogger(__name__)


# @api_view(['POST'])
# def view_mask(request):
#     try:
#         data = json.loads(request.body)
#         mask_url = data['mask_url']
#         logger.info('Received mask URL: %s', mask_url)
#         # Process the mask_url as needed
#         return JsonResponse({'status': 'success', 'mask_url': mask_url})
#     except Exception as e:
#         logger.error('Error processing view_mask: %s', e)
#         return JsonResponse({'error': 'Error processing request'}, status=400)

@api_view(['POST'])
def view_mask(request):
    structure_dir = os.path.join(settings.MEDIA_ROOT, str(request.user), 'masks', 'structures')
    if not os.path.exists(structure_dir):
        os.makedirs(structure_dir)

    mask_path = unquote(request.data.get('mask_url'))
    mask_url = os.path.join(settings.MEDIA_URL, mask_path)
    mask_id = request.data.get('mask_id')


    try:
        structures = UNetMaskStructure.objects.filter(unet_mask_id=mask_id)
        if not structures.exists():
            # No structures => create them
            unetmask = UNetMask.objects.get(id=mask_id)
            mask_np = np.load(unetmask.mask_npy_path)
            filename = unetmask.mask_img_filename.rsplit('.', 1)[0]
            classes = ["IVD", "PE", "TS", "AAP"]

            for i in range(1, mask_np.shape[1]):
                class_fname = filename + '_' + classes[i - 1] + '.png'
                class_save_path = os.path.join(structure_dir, class_fname)

                # Create the new structure
                structure = UNetMaskStructure()
                structure.unet_mask = unetmask
                structure.height, structure.width = np.squeeze(mask_np)[i].shape
                structure.filename = class_fname
                structure.path = class_save_path
                structure.structure = classes[i - 1]
                structure.save()

                # Save the partial mask image
                plt.imsave(class_save_path, np.squeeze(mask_np)[i], cmap='gray')

            # Re-query after creation
            structures = UNetMaskStructure.objects.filter(unet_mask_id=mask_id)

        # Now build a list of paths
        mask_class_paths = []
        for structure in structures:
            mask_class_paths.append(str(structure.path))

        return Response({'mask_url': mask_url, 'mask_class_paths': mask_class_paths})

    except UNetMask.DoesNotExist:
        return Response({'error': 'UNetMask not found'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])  # Only POST allowed
def upload_mask(request):
    """
    Receives an array of 'structures', each containing:
      {
        "label": "IVD" or "PE" etc.,
        "points": [ [x1,y1], [x2,y2], ... ]
      }
    and creates a discrete 320x320 'edited_mask' by drawing them (via fillPoly).
    Then it one-hot encodes that mask, saves the images/files, and creates DB records.
    """
    try:
        # 1) Gather data from request
        structures = request.data.get('structures', [])
        canvas_height = request.data.get('height', None)
        canvas_width = request.data.get('width', None)
        mri_id = request.session.get('selected_mri_id', None)
        if not mri_id:
            return JsonResponse({'success': False, 'error': 'No MRI selected in session'}, status=400)

        # 2) Prepare a blank 320x320 mask
        edited_mask = np.zeros((320, 320), dtype=np.uint8)

        # Scale factors: presumably original was 500x500 -> now 320x320
        scale_x = 320.0 / canvas_width
        scale_y = 320.0 / canvas_height

        # 3) Draw polygons
        for structure in structures:
            label = structure.get('label', '')
            pts = structure.get('points', [])

            # Convert to float array
            pts_array = np.array(pts, dtype=np.float32)
            if pts_array.size == 0:
                continue  # skip if no points

            # Scale coordinates
            pts_array[:, 0] *= scale_x
            pts_array[:, 1] *= scale_y

            # Round and reshape for fillPoly
            pts_array = np.rint(pts_array).astype(np.int32).reshape((-1, 1, 2))
            # Fill with the corresponding grayscale value or 0 if not found
            color_val = STRUCT_COLORS.get(label, 0)
            cv2.fillPoly(edited_mask, [pts_array], color_val)

        # 4) Prepare directories
        user_dir = os.path.join(settings.MEDIA_ROOT, str(request.user))
        edited_mask_dir = os.path.join(user_dir, 'masks', 'edited')
        edited_mask_np_dir = os.path.join(user_dir, 'masks', 'numpy')
        edited_structure_dir = os.path.join(user_dir, 'masks', 'structures')

        for directory in [edited_mask_dir, edited_mask_np_dir, edited_structure_dir]:
            os.makedirs(directory, exist_ok=True)

        # 5) Fetch the MRI record
        mri = MRI.objects.get(id=mri_id)

        # 6) Generate filenames with a timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name, ext = os.path.splitext(mri.filename)
        mask_filename = f"{base_name}_{timestamp}.png"
        mask_np_filename = f"{base_name}_{timestamp}.npy"

        mask_path = os.path.join(edited_mask_dir, mask_filename)
        mask_np_path = os.path.join(edited_mask_np_dir, mask_np_filename)

        # 7) Convert to one-hot
        mask_np = one_hot_encode_masks(edited_mask)

        # 8) Save the raw mask (edited_mask) and the one-hot .npy
        plt.imsave(mask_path, edited_mask, cmap='gray')
        np.save(mask_np_path, mask_np)

        # 9) Create UNetMask record
        unetmask = UNetMask.objects.create(
            MRI=mri,
            mask_img_filename=mask_filename,
            mask_npy_filename=mask_np_filename,
            mask_img_path=mask_path,
            mask_npy_path=mask_np_path,
            mask_version='edited',
            edited=True,
            width=edited_mask.shape[1],   # width = 320
            height=edited_mask.shape[0],  # height = 320
        )

        # 10) Create structure images from the channels in mask_np
        classes = ["IVD", "PE", "TS", "AAP"]
        # mask_np is typically shape (1, num_classes, H, W) or (num_classes, H, W)
        # let's assume shape is (1, num_classes, 320, 320)

        # i=0 might be background, so skip it and start from i=1
        for i in range(1, mask_np.shape[1]):
            class_label = classes[i - 1] if i - 1 < len(classes) else f"class{i}"

            class_fname = f"{base_name}_{class_label}_{timestamp}.png"
            class_save_path = os.path.join(edited_structure_dir, class_fname)

            # The channel might be mask_np[0,i,:,:], shape (320,320)
            channel_img = mask_np[0, i, :, :]

            plt.imsave(class_save_path, channel_img, cmap='gray')

            # Create UNetMaskStructure record
            UNetMaskStructure.objects.create(
                unet_mask=unetmask,
                height=channel_img.shape[0],
                width=channel_img.shape[1],
                filename=class_fname,
                path=class_save_path,
                structure=class_label
            )

        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@api_view(['POST'])
def get_control_points(request):
    mask_id = request.data.get('mask_id')
    mask_path = request.data.get('mask_url')
    try:
        structures = UNetMaskStructure.objects.filter(unet_mask_id=mask_id)
        structure_cnt_points = {}
        for structure in structures:
            path = str(structure.path)
            cls = structure.structure
            mask = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
            mask = cv2.resize(mask, (500, 500), interpolation=cv2.INTER_NEAREST_EXACT)
            cnts, hier = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            cnts = sorted(cnts, key=cv2.contourArea)
            structure_cnt_points[cls] = [cnt.tolist() for cnt in cnts]
    except UNetMaskStructure.DoesNotExist:
        return Response({'error': 'UNetMaskStructure not found'}, status=404)

    return JsonResponse({'cls_cnt': structure_cnt_points})


@api_view(['POST'])
def process_image(request):
    if request.method == 'POST':
        mask_url = None
        selected_mri_id = request.session.get('selected_mri_id', None)
        selected_mri = MRI.objects.get(id=selected_mri_id)
        try:
            unetmask = UNetMask.objects.get(
                MRI=selected_mri_id, edited=False, mask_version="original"
            )
            mask_url = unetmask.mask_img_path.url  # or unetmask.path if it's a CharField
        except UNetMask.DoesNotExist:
            # If we don’t find a matching record, handle logic here:

            mri_path = request.session.get('selected_mri_path', None)
            mri_path = os.path.join(settings.MEDIA_ROOT, unquote(mri_path))

            img_mat = cv2.imread(mri_path, cv2.IMREAD_GRAYSCALE)[np.newaxis, ...].astype(np.float32)
            img_mat = img_mat[np.newaxis, ...]
            with torch.no_grad():
                img_mat = torch.from_numpy(img_mat)
                img_mat = img_mat.to(device)
                mask = model(img_mat)
            mask_np = mask.cpu().numpy()
            mask_img = np.squeeze(np.argmax(mask_np, axis=1))

            save_dir_mask_img = os.path.join(settings.MEDIA_ROOT, str(request.user), 'masks', 'original')
            save_dir_mask_npy = os.path.join(settings.MEDIA_ROOT, str(request.user), 'masks', 'numpy')
            if not os.path.exists(save_dir_mask_img):
                os.makedirs(save_dir_mask_img)
            if not os.path.exists(save_dir_mask_npy):
                os.makedirs(save_dir_mask_npy)

            mask_img_filename = mri_path.split('/')[-1].split('.')[0] + '.png'
            mask_npy_filename = mask_img_filename.split('.')[0] + '.npy'

            mask_img_path = os.path.join(save_dir_mask_img, mask_img_filename)
            mask_npy_path = os.path.join(save_dir_mask_npy, mask_npy_filename)

            mask_url = os.path.join(str(request.user), 'masks', 'original', mask_img_filename)

            unetmask = UNetMask()
            unetmask.mask_img_filename = mask_img_filename
            unetmask.mask_npy_filename = mask_npy_filename
            unetmask.mask_img_path.name = mask_url
            unetmask.mask_npy_path = mask_npy_path
            unetmask.width, unetmask.height = mask_img.shape
            unetmask.mask_version = 'original'
            unetmask.edited = False
            unetmask.MRI = selected_mri

            plt.imsave(mask_img_path, mask_img, cmap='gray')
            np.save(mask_npy_path, mask_np)

            unetmask.save()

        return Response({'mask_url': mask_url, 'mask_id': unetmask.id})

    return Response({'error': 'Invalid request'}, status=400)

@api_view(['POST'])
def process_mri_for_view(request):
    temp_save_dir = os.path.join(settings.MEDIA_ROOT, str(request.user), 'temp')
    os.makedirs(temp_save_dir, exist_ok=True)

    saved_files = []

    # Process JPEG/PNG images (saved directly)
    if 'imageInput' in request.FILES:
        image_files = request.FILES.getlist('imageInput')
        for file in image_files:
            file_path = os.path.join(temp_save_dir, file.name)
            with open(file_path, 'wb+') as destination:
                for chunk in file.chunks():
                    destination.write(chunk)
            file_path = os.path.join(settings.MEDIA_URL, str(request.user), 'temp', file.name)
            saved_files.append(file_path)

    # Process DICOM/IMA files (single or multiple) uploaded via 'dicomInput'
    if 'dicomInput' in request.FILES:
        dicom_files = request.FILES.getlist('dicomInput')
        for file in dicom_files:
            base_name = os.path.splitext(file.name)[0]
            output_file_name = base_name + '.png'
            output_path = os.path.join(temp_save_dir, output_file_name)
            # Convert the DICOM file to a PNG.
            dicom_to_png(file, output_path)
            output_path = os.path.join(settings.MEDIA_URL, str(request.user), 'temp', output_file_name)
            saved_files.append(output_path)

    # Process directory of DICOM/IMA files uploaded via 'dicomDirInput'
    if 'dicomDirInput' in request.FILES:
        dicom_dir_files = request.FILES.getlist('dicomDirInput')
        for file in dicom_dir_files:
            base_name = os.path.splitext(file.name)[0]
            output_file_name = base_name + '.png'
            output_path = os.path.join(temp_save_dir, output_file_name)
            dicom_to_png(file, output_path)
            output_path = os.path.join(settings.MEDIA_URL, str(request.user), 'temp', output_file_name)
            saved_files.append(output_path)

    return Response({
        "message": "Files processed and saved successfully.",
        "files": saved_files,
    })


@api_view(['POST'])
def save_image(request):
    if request.method == 'POST':
        user_str = str(request.user)
        # Build the permanent directory: MEDIA_ROOT/<username>/images
        save_dir_img = os.path.join(settings.MEDIA_ROOT, user_str, 'images')
        if not os.path.exists(save_dir_img):
            os.makedirs(save_dir_img)

        # Get the list of processed image URLs sent from the client.
        # These should be strings like "/media/<username>/images/temp/filename.png"
        selected_files = request.POST.getlist('selected_files')
        if not selected_files:
            return Response({"error": "No selected files provided."}, status=400)

        for file_url in selected_files:
            # Remove the MEDIA_URL prefix (e.g. "/media/") to get the relative path.
            if file_url.startswith(settings.MEDIA_URL):
                relative_temp_path = file_url[len(settings.MEDIA_URL):]
            else:
                relative_temp_path = file_url

            # Build the absolute path to the temporary file.
            temp_file_path = os.path.join(settings.MEDIA_ROOT, relative_temp_path)
            if not os.path.exists(temp_file_path):
                # Skip files that don't exist.
                continue

            # Destination filename remains the same (assumed to be PNG)
            new_filename = os.path.basename(temp_file_path)
            dest_file_path = os.path.join(save_dir_img, new_filename)

            try:
                # Open the image from the temporary file
                im = Image.open(temp_file_path)
                # Check if size is not (320,320)
                if im.size != (320, 320):
                    im = im.resize((320, 320), Image.ANTIALIAS)
                # Optionally ensure the image is in grayscale
                im = im.convert('L')
                # Save the processed image as PNG to the destination file
                im.save(dest_file_path, format='PNG')
            except Exception as e:
                # Optionally log error and skip this file
                print(f"Error processing file {temp_file_path}: {e}")
                continue

            # Build relative permanent path (e.g., "<username>/images/filename.png")
            relative_permanent_path = os.path.join(user_str, 'images', new_filename)

            # Create a new MRI instance.
            mriDB = MRI()
            mriDB.filename = new_filename
            mriDB.filetype = request.POST.get('imgType', 'image/png')
            mriDB.width = 320
            mriDB.height = 320
            mriDB.user = request.user
            mriDB.path.name = relative_permanent_path  # Assuming MRI.path is a FileField/ImageField
            mriDB.save()

            print('Saved:', new_filename)

        # Delete all files in the temporary folder: MEDIA_ROOT/<username>/images/temp
        temp_folder = os.path.join(settings.MEDIA_ROOT, user_str, 'images', 'temp')
        if os.path.exists(temp_folder):
            shutil.rmtree(temp_folder)
            print("Deleted temp folder")

        # After processing, redirect to home
        return redirect('/')

    return Response({"error": "Invalid request method."}, status=405)

@api_view(['GET'])
def get_mri_path(request):
    """
    Retrieve an MRI object by its ID from the query parameters,
    store that ID in the user's session, and return the path.
    """

    # 1) Read mri_id from ?mri_id=<some_id>
    mri_id = request.GET.get('mri_id')
    if not mri_id:
        return Response({'error': 'No mri_id provided'}, status=400)

    # 2) Fetch the MRI record
    try:
        mri_obj = MRI.objects.get(pk=mri_id)
    except MRI.DoesNotExist:
        return Response({'error': f'MRI with id={mri_id} not found'}, status=404)

    # 3) Store the ID in the session
    # Each user's session is different, so no risk of overwriting across users
    request.session['selected_mri_id'] = mri_id
    request.session['selected_mri_path'] = str(mri_obj.path)

    # 4) Build the path you want to return to the front-end
    #    If `mri_obj.path` is an ImageField or FileField, you can do `mri_obj.path.url`
    #    If it's just a string path, you can return it as-is
    file_path = None
    if hasattr(mri_obj.path, 'url'):
        # If it's an ImageField or FileField
        file_path = mri_obj.path.url
    else:
        # If it's a CharField storing path
        file_path = str(mri_obj.path)

    return Response({
        'path': file_path
    })


def del_image(request):
    if request.method == 'POST':
        return redirect('/')
    return render(request, "delImg.html")

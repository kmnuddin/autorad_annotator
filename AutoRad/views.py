import datetime
import json
import os
from urllib.parse import unquote
from io import BytesIO
import cv2
import matplotlib.pyplot as plt
import numpy as np
import torch
import pydicom
from PIL import Image
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.views.generic.edit import CreateView
from rest_framework.decorators import api_view
from rest_framework.response import Response

from AutoRad.accounts.forms import CustomUserCreationForm
# import customized class models
from .models import MRI, UNetMask, UNetMaskStructure, Patient
from .utils import model, device
from .utils import one_hot_encode_masks, dicom_to_png_bytes, extract_mri_metadata, extract_patient_metadata

SELECTED_MRI_ID = None

STRUCT_COLORS = {
    'IVD': 64,
    'PE': 128,
    'TS': 192,
    'AAP': 255
}


class SignUpView(CreateView):
    form_class = CustomUserCreationForm
    template_name = 'registration/signup.html'
    success_url = reverse_lazy('home')  # Redirect to the home page after signup

    def form_valid(self, form):
        response = super().form_valid(form)
        user = form.save()
        login(self.request, user)  # Automatically log in the user after registration
        return response


@login_required
def home(request):
    user_institution = (request.user.institution or "").strip().lower()

    # Check if the user is from The University of Memphis
    if user_institution == "the university of memphis":
        images = MRI.objects.all()
    else:
        # Otherwise, only show MRI from users sharing the same institution.
        images = MRI.objects.filter(annotator_inst__iexact=request.user.institution)

    context = {'images': images}
    return render(request, 'home.html', context)


def saveImg(request):
    # Determine the directory of this file (views.py)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    # Construct the path to the institutions.json file in the accounts folder
    institutions_path = os.path.join(base_dir, 'accounts', 'institutions.json')

    try:
        with open(institutions_path, 'r') as f:
            institutions = json.load(f)
    except Exception as e:
        institutions = []
        print("Error loading institutions.json:", e)

    # Get the current user's institution if available
    user_institution = None
    if request.user.is_authenticated:
        user_institution = request.user.institution

    context = {
        'institutions': institutions,  # This should be a list of institution names (or tuples if you prefer)
        'user_institution': user_institution,
    }

    return render(request, 'saveImg.html', context)



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
        mri.modified_at = timezone.now()
        mri.save(update_fields=['modified_at'])


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
            edited_by=request.user,
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

            filename = os.path.basename(mri_path)  # Extracts just the file name from the full path.
            mask_img_filename = os.path.splitext(filename)[0] + '.png'
            mask_npy_filename = os.path.splitext(filename)[0] + '.npy'

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
            unetmask.edited_by = request.user
            unetmask.MRI = selected_mri

            plt.imsave(mask_img_path, mask_img, cmap='gray')
            np.save(mask_npy_path, mask_np)

            unetmask.save()

        return Response({'mask_url': mask_url, 'mask_id': unetmask.id})

    return Response({'error': 'Invalid request'}, status=400)

# @api_view(['POST'])
# def process_mri_for_view(request):
#     temp_save_dir = os.path.join(settings.MEDIA_ROOT, str(request.user), 'temp')
#     os.makedirs(temp_save_dir, exist_ok=True)
#
#     saved_files = []
#     patient_metadata_list = []
#     mri_metadata_list = []
#
#     # Process JPEG/PNG images (saved directly)
#     if 'imageInput' in request.FILES:
#         image_files = request.FILES.getlist('imageInput')
#         for file in image_files:
#             file_path = os.path.join(temp_save_dir, file.name)
#             with open(file_path, 'wb+') as destination:
#                 for chunk in file.chunks():
#                     destination.write(chunk)
#             file_url = os.path.join(settings.MEDIA_URL, str(request.user), 'temp', file.name)
#             saved_files.append(file_url)
#             # No DICOM metadata extraction for standard image files
#
#     # Process DICOM/IMA files (single or multiple) uploaded via 'dicomInput'
#     if 'dicomInput' in request.FILES:
#         dicom_files = request.FILES.getlist('dicomInput')
#         for file in dicom_files:
#             base_name = os.path.splitext(file.name)[0]
#             output_file_name = base_name + '.png'
#             output_path = os.path.join(temp_save_dir, output_file_name)
#             # Convert the DICOM file to a PNG and obtain the pydicom Dataset.
#             ds = dicom_to_png(file, output_path)
#             file_url = os.path.join(settings.MEDIA_URL, str(request.user), 'temp', output_file_name)
#             saved_files.append(file_url)
#             # Extract metadata for this file
#             patient_metadata_list.append(extract_patient_metadata(ds))
#             mri_metadata_list.append(extract_mri_metadata(ds))
#
#     # Process directory of DICOM/IMA files uploaded via 'dicomDirInput'
#     if 'dicomDirInput' in request.FILES:
#         dicom_dir_files = request.FILES.getlist('dicomDirInput')
#         for file in dicom_dir_files:
#             base_name = os.path.splitext(file.name)[0]
#             output_file_name = base_name + '.png'
#             output_path = os.path.join(temp_save_dir, output_file_name)
#             ds = dicom_to_png(file, output_path)
#             file_url = os.path.join(settings.MEDIA_URL, str(request.user), 'temp', output_file_name)
#             saved_files.append(file_url)
#             # Extract metadata for this file
#             patient_metadata_list.append(extract_patient_metadata(ds))
#             mri_metadata_list.append(extract_mri_metadata(ds))
#
#     return Response({
#         "message": "Files processed and saved successfully.",
#         "files": saved_files,
#         "patient_metadata": patient_metadata_list,
#         "mri_metadata": mri_metadata_list,
#     })

@api_view(['POST'])
def process_mri_for_view(request):
    """
    Accepts JPEG/PNG or DICOM/IMA uploads, converts everything to PNG,
    stores them under "<username>/temp/…" in S3, and returns their URLs
    along with any extracted metadata.
    """
    user_folder = f"{request.user.username}/temp"
    saved_files = []
    patient_metadata_list = []
    mri_metadata_list = []

    # helper to save raw bytes into default_storage and return its URL
    def _save_to_s3(filename, bytes_data):
        path = f"{user_folder}/{filename}"
        # overwrite if exists
        if default_storage.exists(path):
            default_storage.delete(path)
        default_storage.save(path, ContentFile(bytes_data))
        return default_storage.url(path)

    # --- 1) plain JPEG/PNG ---
    for field in ('imageInput',):
        if field in request.FILES:
            for fobj in request.FILES.getlist(field):
                # read raw bytes
                raw = fobj.read()
                url = _save_to_s3(fobj.name, raw)
                saved_files.append(url)
                # no DICOM metadata here
    # --- 2) single DICOM ---
    for field in ('dicomInput','dicomDirInput'):
        if field in request.FILES:
            for fobj in request.FILES.getlist(field):
                ds = pydicom.dcmread(BytesIO(fobj.read()))
                png_bytes, ds = dicom_to_png_bytes(ds)
                out_name = os.path.splitext(fobj.name)[0] + ".png"
                url = _save_to_s3(out_name, png_bytes)
                saved_files.append(url)

                # metadata extractors should take the pydicom Dataset
                patient_metadata_list.append(extract_patient_metadata(ds))
                mri_metadata_list.append(extract_mri_metadata(ds))

    return Response({
        "message": "Files processed and saved successfully.",
        "files":             saved_files,
        "patient_metadata":  patient_metadata_list,
        "mri_metadata":      mri_metadata_list,
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
        selected_files = request.POST.getlist('selected_files')
        if not selected_files:
            return Response({"error": "No selected files provided."}, status=400)

        # Retrieve metadata arrays (as JSON strings) and parse them.
        # For standard images, these may be empty.
        patient_meta_json = request.POST.get('patient_metadata', '[]')
        mri_meta_json = request.POST.get('mri_metadata', '[]')
        try:
            patient_meta_list = json.loads(patient_meta_json)
            mri_meta_list = json.loads(mri_meta_json)
        except Exception as e:
            return Response({"error": "Invalid metadata format."}, status=400)

        # Determine the overall image type from the POST data.
        upload_img_type = request.POST.get('imgType', 'image/png').lower()

        for idx, file_url in enumerate(selected_files):
            # Remove the MEDIA_URL prefix (e.g. "/media/") to get the relative path.
            if file_url.startswith(settings.MEDIA_URL):
                relative_temp_path = file_url[len(settings.MEDIA_URL):]
            else:
                relative_temp_path = file_url

            # Build the absolute path to the temporary file.
            temp_file_path = os.path.join(settings.MEDIA_ROOT, relative_temp_path)
            if not os.path.exists(temp_file_path):
                continue

            # Destination filename remains the same (assumed to be PNG)
            new_filename = os.path.basename(temp_file_path)
            dest_file_path = os.path.join(save_dir_img, new_filename)

            try:
                # Open the image from the temporary file
                im = Image.open(temp_file_path)
                # Resize if needed
                if im.size != (320, 320):
                    try:
                        resample = Image.Resampling.LANCZOS  # For Pillow >= 10
                    except AttributeError:
                        resample = Image.LANCZOS  # For older versions
                    im = im.resize((320, 320), resample)
                # Convert to grayscale
                im = im.convert('L')
                # Save processed image as PNG to the permanent folder
                im.save(dest_file_path, format='PNG')
            except Exception as e:
                print(f"Error processing file {temp_file_path}: {e}")
                continue

            # Build relative permanent path (e.g., "<username>/images/filename.png")
            relative_permanent_path = os.path.join(user_str, 'images', new_filename)

            # For DICOM/IMA files, extract metadata and save Patient record.
            # For standard image files (JPEG/PNG), skip patient metadata.
            if upload_img_type in ['dicom', 'ima']:
                try:
                    current_patient_meta = patient_meta_list[idx]
                except IndexError:
                    current_patient_meta = {}
                try:
                    current_mri_meta = mri_meta_list[idx]
                except IndexError:
                    current_mri_meta = {}

                # Determine external patient ID from metadata.
                external_patient_id = current_patient_meta.get('patient_id', '').strip()
                if external_patient_id:
                    # Look up an existing Patient record for this user.
                    patient_obj = Patient.objects.filter(id_from_inst=external_patient_id, user=request.user).first()
                    if not patient_obj:
                        patient_obj = Patient.objects.create(
                            id_from_inst=external_patient_id,
                            age=current_patient_meta.get('age', ''),
                            weight=current_patient_meta.get('weight', None),
                            height=current_patient_meta.get('height', None),
                            sex=current_patient_meta.get('sex', ''),
                            user=request.user,
                            from_module=current_patient_meta.get('from_module', '')
                        )
                else:
                    # If no external patient ID, you may decide to create a default record.
                    default_id = "N/A"
                    patient_obj = Patient.objects.filter(id_from_inst=default_id, user=request.user).first()
                    if not patient_obj:
                        patient_obj = Patient.objects.create(
                            id_from_inst=default_id,
                            user=request.user
                        )
            else:
                # For JPEG/PNG images, do not create a patient record.
                patient_obj = None
                # Optionally, you might clear out any metadata:
                current_mri_meta = {}

            # Retrieve the module and annotator institution from POST data.
            uploaded_module = request.POST.get('uploaded_module', '').strip()  # No default here; client must supply a value.
            annotator_institution = request.POST.get('annotator_institution', '').strip()
            if not annotator_institution:
                annotator_institution = request.user.institution or ''

            # Create a new MRI instance.
            mriDB = MRI()
            mriDB.filename = new_filename
            mriDB.filetype = request.POST.get('imgType', 'image/png')
            mriDB.width = 320
            mriDB.height = 320
            mriDB.user = request.user
            mriDB.path.name = relative_permanent_path
            # Assign MRI metadata fields only if available (for DICOM/IMA)
            mriDB.modality = current_mri_meta.get('modality', '')
            mriDB.manufacturer = current_mri_meta.get('manufacturer', '')
            mriDB.pixel_spacing = current_mri_meta.get('pixel_spacing', '')
            mriDB.protocol_name = current_mri_meta.get('protocol_name', '')
            mriDB.mri_type = current_mri_meta.get('mri_type', '')
            mriDB.orientation = current_mri_meta.get('orientation', '')
            mriDB.repetition_time = current_mri_meta.get('repetition_time', '')
            mriDB.echo_time = current_mri_meta.get('echo_time', '')
            mriDB.inversion_time = current_mri_meta.get('inversion_time', '')
            mriDB.flip_angle = current_mri_meta.get('flip_angle', '')
            mriDB.magnetic_field_strength = current_mri_meta.get('magnetic_field_strength', '')
            mriDB.acquisition_matrix = current_mri_meta.get('acquisition_matrix', '')
            mriDB.pixel_bandwidth = current_mri_meta.get('pixel_bandwidth', '')
            mriDB.fov = current_mri_meta.get('fov', '')
            mriDB.module = uploaded_module
            mriDB.annotator_inst = annotator_institution

            # Link MRI to the Patient if applicable; for standard images, leave as None.
            mriDB.Patient = patient_obj
            mriDB.save()

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

@api_view(['GET'])
def delete(request, mri_id):
    if not mri_id:
        return Response({'error': 'No mri_id'})
    masks = UNetMask.objects.filter(MRI_id=mri_id)
    if masks.exists():
        for mask in masks:
            structures = UNetMaskStructure.objects.filter(unet_mask=mask)
            structures.delete()
        masks.delete()
    mri = MRI.objects.get(pk=mri_id)
    mri.delete()
    return redirect('/')

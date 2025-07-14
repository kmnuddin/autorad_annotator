import datetime
import gc
import json
import os
from io import BytesIO
from urllib.parse import urlparse
from itertools import chain
from operator import attrgetter

import cv2
import numpy as np
import pydicom
import torch
from PIL import Image
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic.edit import CreateView
from rest_framework.decorators import api_view
from rest_framework.response import Response

from AutoRad.accounts.forms import CustomUserCreationForm
# import customized class models
from .models import MRI, UNetMask, UNetMaskStructure, Patient
from .utils import model, device
from .utils import one_hot_encode_masks, dicom_to_png_bytes, extract_mri_metadata, extract_patient_metadata, get_tag_pipeline, load_lumbar_model

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
    user_inst = (request.user.institution or "").strip().lower()

    # Base queryset, already ordered by creation time
    qs = MRI.objects.select_related('user', 'Patient').order_by('created_at')
    if user_inst != "the university of memphis":
        qs = qs.filter(user__institution__iexact=user_inst)

    # Separate the two cases
    assessment_qs = qs.filter(module='assessment_reporting')
    other_qs = qs.exclude(module='assessment_reporting')

    # Pick only the first MRI per patient for assessment_reporting
    first_by_patient = {}
    for m in assessment_qs:
        pid = m.Patient_id
        if pid not in first_by_patient:
            first_by_patient[pid] = m

    # Combine:
    images = list(other_qs) + list(first_by_patient.values())
    # (Optional) Sort the combined list by created_at if you want global ordering:
    images.sort(key=attrgetter('created_at'))

    return render(request, 'home.html', {
        'images': images,
    })


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

    # 2. Figure out the user’s institution
    user_institution = None
    if request.user.is_authenticated:
        user_institution = (request.user.institution or "").strip()

    # 3. Select which patients to show
    if user_institution and user_institution.lower() == "the university of memphis":
        # Memphis sees *all* patients
        patients = Patient.objects.all()
    elif user_institution:
        # everyone else sees only patients annotated under their institution
        patients = Patient.objects.filter(annotator_inst__iexact=user_institution)
    else:
        # not logged in (or no institution) → no patients
        patients = Patient.objects.none()

    # 4. Render your template
    return render(request, 'saveImg.html', {
        'institutions': institutions,
        'user_institution': user_institution,
        'patients': patients,
    })

@login_required
def assessment_view(request, patient_id):
    patient_mris = MRI.objects.filter(Patient_id=patient_id).order_by('created_at')
    return render(request, 'assessment.html', {
        'patient_mris': patient_mris,
        'patient': patient_mris.first().Patient if patient_mris.exists() else None,
    })


@login_required
def segmentation(request, mri_id):
    """
    Retrieve an MRI object by its ID from the query parameters,
    store that ID in the user's session, and return the path.
    """
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

    return render(request, 'segmentation.html', {
        'path': file_path
    })


@api_view(['POST'])
def view_mask(request):
    mask_id = request.data.get('mask_id')
    mask_url = request.data.get('mask_url')
    if not mask_id or not mask_url:
        return Response({'error': 'mask_id and mask_url required'}, status=400)

    # try to fetch existing structures
    structures = UNetMaskStructure.objects.filter(unet_mask_id=mask_id)
    if not structures.exists():
        # load the base UNetMask record
        try:
            unetmask = UNetMask.objects.get(id=mask_id)
        except UNetMask.DoesNotExist:
            return Response({'error': 'UNetMask not found'}, status=404)

        # Read the .npy from S3
        npy_key = unetmask.mask_npy_path
        try:
            with default_storage.open(npy_key, 'rb') as f:
                mask_np = np.load(f)
        except Exception as e:
            return Response({'error': f'Could not load mask array: {e}'}, status=500)

        # mask_np shape is (1, C, H, W)
        classes = ["IVD", "PE", "TS", "AAP"]
        user_str = str(request.user)

        for cls_idx, cls_name in enumerate(classes, start=1):
            # slice out this plane
            plane = mask_np[0, cls_idx].astype(np.uint8)
            h, w = plane.shape

            # BUILD CONTRAST-STRETCHED IMAGE
            minv, maxv = plane.min(), plane.max()
            if maxv > minv:
                stretched = ((plane - minv) / (maxv - minv) * 255).astype(np.uint8)
            else:
                stretched = plane
            im = Image.fromarray(stretched, mode='L')

            # render to PNG in‑memory
            buf = BytesIO()
            im.save(buf, format='PNG')
            buf.seek(0)

            # persist to S3
            png_key = f"{user_str}/masks/structures/{mask_id}/{cls_name}.png"
            default_storage.save(png_key, ContentFile(buf.read()))
            buf.close()

            # record in the DB
            s = UNetMaskStructure(
                unet_mask=unetmask,
                structure=cls_name,
                filename=f"{cls_name}.png",
                width=w,
                height=h,
            )
            # store the S3 key so that `s.path.url` will resolve
            s.path.name = png_key
            s.save()

        structures = UNetMaskStructure.objects.filter(unet_mask_id=mask_id)

    # Now return all the structure URLs
    mask_class_urls = [default_storage.url(s.path.name) for s in structures]

    return Response({
        'mask_url': mask_url,
        'mask_class_urls': mask_class_urls,
    })


@api_view(['POST'])
def upload_mask(request):
    """
    Receives `structures`, a list of {label, points: [...]}, plus canvas size.
    Draws them into a 320×320 uint8 mask, one‑hot encodes, pushes PNG+NPY to S3,
    and makes UNetMask + UNetMaskStructure records.
    """
    # 1) grab the polygon data & session MRI
    structures = request.data.get('structures', [])
    canvas_h = float(request.data.get('height', 1))
    canvas_w = float(request.data.get('width', 1))
    mri_id = request.session.get('selected_mri_id')
    if not mri_id:
        return Response({'success': False, 'error': 'No MRI selected'}, status=400)

    # 2) make a blank 320×320 label image
    edited_mask = np.zeros((320, 320), dtype=np.uint8)
    sx = 320.0 / canvas_w
    sy = 320.0 / canvas_h

    # 3) draw each polygon
    for struct in structures:
        pts = np.array(struct.get('points', []), dtype=np.float32)
        if pts.size == 0:
            continue
        # scale coords, round to ints, reshape for fillPoly
        pts[:, 0] *= sx
        pts[:, 1] *= sy
        pts = np.rint(pts).astype(np.int32).reshape(-1, 1, 2)
        color = STRUCT_COLORS.get(struct.get('label', ''), 0)
        cv2.fillPoly(edited_mask, [pts], color)

    # 4) fetch & touch the MRI record
    mri = MRI.objects.get(pk=mri_id)
    mri.modified_at = timezone.now()
    mri.save(update_fields=['modified_at'])

    # 5) build S3 key prefixes
    user_str = str(request.user)
    ts = datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    base, _ = mri.filename.rsplit('.', 1)
    png_key = f"{user_str}/masks/edited/{base}_{ts}.png"
    npy_key = f"{user_str}/masks/numpy/{base}_{ts}.npy"
    struct_dir = f"{user_str}/masks/structures/{base}_{ts}"

    # 6) one‑hot encode
    mask_np = one_hot_encode_masks(edited_mask)  # shape (1, C, 320, 320)

    # 7) save the raw mask PNG
    buf = BytesIO()
    # plt.imsave expects a filename, but PIL is simpler here:

    Image.fromarray(edited_mask).save(buf, format='PNG')
    default_storage.save(png_key, ContentFile(buf.getvalue()))
    buf.close()

    # 8) save the .npy
    buf = BytesIO()
    np.save(buf, mask_np)
    default_storage.save(npy_key, ContentFile(buf.getvalue()))
    buf.close()

    # 9) create UNetMask row
    unetmask = UNetMask.objects.create(
        MRI=mri,
        mask_version='edited',
        edited=True,
        edited_by=request.user,
        mask_img_filename=png_key.rsplit('/', 1)[-1],
        mask_npy_filename=npy_key.rsplit('/', 1)[-1],
        mask_img_path=png_key,
        mask_npy_path=npy_key,
        width=320,
        height=320,
    )

    # 10) for each channel >0, emit a structure PNG + record
    classes = ["IVD", "PE", "TS", "AAP"]
    for i, label in enumerate(classes, start=1):
        plane = mask_np[0, i, :, :].astype(np.uint8)
        struct_key = f"{struct_dir}/{label}.png"
        buf = BytesIO()
        Image.fromarray(plane).save(buf, format='PNG')
        default_storage.save(struct_key, ContentFile(buf.getvalue()))
        buf.close()

        UNetMaskStructure.objects.create(
            unet_mask=unetmask,
            structure=label,
            filename=f"{label}.png",
            path=struct_key,
            width=320,
            height=320,
        )

    return Response({'success': True})


@api_view(['POST'])
def get_control_points(request):
    mask_id = request.data.get('mask_id')
    mask_url = request.data.get('mask_url')

    structures = UNetMaskStructure.objects.filter(unet_mask_id=mask_id)
    structure_cnt_points = {}

    for struct in structures:
        cls = struct.structure
        # Instead of struct.path.name, just grab struct.path directly:
        key = str(struct.path)

        # load raw bytes from S3
        try:
            with default_storage.open(key, 'rb') as f:
                data = f.read()
        except Exception as e:
            return Response(
                {"error": f"Could not load structure image {cls}: {e}"},
                status=500
            )

        # decode into a grayscale numpy array
        arr = np.frombuffer(data, dtype=np.uint8)
        mask = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
        if mask is None:
            return Response(
                {"error": f"cv2 failed to decode structure image {cls}"},
                status=500
            )

        # resize and find contours as before
        mask = cv2.resize(mask, (500, 500), interpolation=cv2.INTER_NEAREST_EXACT)
        cnts, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        cnts = sorted(cnts, key=cv2.contourArea)

        structure_cnt_points[cls] = [cnt.tolist() for cnt in cnts]

    return JsonResponse({'cls_cnt': structure_cnt_points})


@api_view(['POST'])
def process_image(request):
    if request.method != 'POST':
        return Response({'error': 'Invalid request'}, status=400)

    # which MRI are we segmenting?
    selected_mri_id = request.session.get('selected_mri_id')
    if not selected_mri_id:
        return Response({'error': 'No MRI selected in session'}, status=400)
    try:
        selected_mri = MRI.objects.get(id=selected_mri_id)
    except MRI.DoesNotExist:
        return Response({'error': 'MRI not found'}, status=404)

    # do we already have an “original” mask?
    try:
        unetmask = UNetMask.objects.get(
            MRI=selected_mri,
            edited=False,
            mask_version='original'
        )
        return Response({
            'mask_url': unetmask.mask_img_path.url,
            'mask_id': unetmask.id
        })
    except UNetMask.DoesNotExist:
        pass  # fall through to generate one now

    # load the image from wherever we stored it (session holds its MEDIA key)
    mri_key = request.session.get('selected_mri_path')
    if not mri_key or not default_storage.exists(mri_key):
        return Response({'error': 'MRI file not found in storage'}, status=404)

    # read raw bytes and decode
    with default_storage.open(mri_key, 'rb') as f:
        raw = f.read()

    # cv2 wants a filesystem path, so write into a temp BytesIO-backed file, decode, then delete
    # (small overhead but avoids local disk)
    tmp_buf = BytesIO(raw)
    # OpenCV can't read from BytesIO directly, so:
    tmp_buf.seek(0)
    arr = cv2.imdecode(np.frombuffer(tmp_buf.read(), np.uint8), cv2.IMREAD_GRAYSCALE)
    if arr is None:
        return Response({'error': 'Failed to decode MRI image'}, status=400)

    # prepare for the model (1×1×H×W float32)
    img_mat = arr[np.newaxis, ...].astype(np.float32)[np.newaxis, ...]

    with torch.no_grad():
        inp = torch.from_numpy(img_mat).to(device)
        mask = model(inp)
    mask_np = mask.cpu().numpy()
    # assume categorical mask: pick argmax across channel
    mask_img = np.squeeze(np.argmax(mask_np, axis=1))

    user_str = str(request.user)
    base_path = f"{user_str}/masks"

    # --- SAVE PNG to S3 ---
    png_key = f"{base_path}/original/{selected_mri_id}.png"
    png_buf = BytesIO()
    # use PIL for reliable PNG output:
    minv, maxv = mask_img.min(), mask_img.max()
    if maxv > minv:
        stretched = ((mask_img - minv) / (maxv - minv) * 255.0).astype(np.uint8)
    else:
        # degenerate (all‐flat) case
        stretched = np.clip(mask_img, 0, 255).astype(np.uint8)

    # 2) convert to PIL
    im = Image.fromarray(stretched, mode='L')

    im.save(png_buf, format='PNG')
    png_buf.seek(0)
    default_storage.save(png_key, ContentFile(png_buf.read()))
    png_buf.close()

    # --- SAVE .npy to S3 ---
    npy_key = f"{base_path}/numpy/{selected_mri_id}.npy"
    npy_buf = BytesIO()
    np.save(npy_buf, mask_np)
    npy_buf.seek(0)
    default_storage.save(npy_key, ContentFile(npy_buf.read()))

    # record in your DB
    unetmask = UNetMask(
        MRI=selected_mri,
        mask_version='original',
        edited=False,
        edited_by=request.user,
        width=mask_img.shape[1],
        height=mask_img.shape[0],
        mask_img_filename=f"{selected_mri_id}.png",
        mask_npy_filename=f"{selected_mri_id}.npy",
    )
    # StringFields or FileFields should use the storage key
    unetmask.mask_img_path = png_key
    unetmask.mask_npy_path = npy_key
    unetmask.save()

    return Response({
        'mask_url': default_storage.url(png_key),
        'mask_id': unetmask.id
    })


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
    for field in ('dicomInput', 'dicomDirInput'):
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
        "files": saved_files,
        "patient_metadata": patient_metadata_list,
        "mri_metadata": mri_metadata_list,
    })


@api_view(['POST'])
def save_image(request):
    if request.method != 'POST':
        return Response({"error": "Invalid request method."}, status=405)

    user_str = str(request.user)
    selected_files = request.POST.getlist('selected_files')

    if not selected_files:
        return Response({"error": "No selected files provided."}, status=400)

    try:
        patient_meta_list = json.loads(request.POST.get('patient_metadata', '[]'))
        mri_meta_list = json.loads(request.POST.get('mri_metadata', '[]'))
    except json.JSONDecodeError:
        return Response({"error": "Invalid metadata format."}, status=400)

    upload_img_type = request.POST.get('imgType', 'image/png').lower()
    uploaded_module = request.POST.get('uploaded_module', '').strip()
    annotator_inst = (request.POST.get('annotator_institution', '').strip()
                      or request.user.institution or '')
    patient_choice = request.POST.get('patient_db', 'new')

    # --- 1) Resolve or create exactly one Patient for this batch ---
    if upload_img_type in ('dicom', 'ima'):
        if patient_choice != 'new':
            # user picked an existing patient
            try:
                patient_obj = Patient.objects.get(
                    pk=int(patient_choice),
                    user=request.user
                )
            except (Patient.DoesNotExist, ValueError):
                return Response(
                    {"error": f"Selected patient ({patient_choice}) not found."},
                    status=400
                )
        else:
            # always create exactly one new Patient
            first_meta = patient_meta_list[0] if patient_meta_list else {}
            external_id = first_meta.get('patient_id', '').strip() or "N/A"
            patient_obj = Patient.objects.create(
                id_from_inst=external_id,
                age=first_meta.get('age', ''),
                weight=first_meta.get('weight', None),
                height=first_meta.get('height', None),
                sex=first_meta.get('sex', ''),
                user=request.user,
                from_module=uploaded_module,
                annotator_inst=annotator_inst,
            )
    else:
        # JPEG/PNG uploads skip patient entirely
        patient_obj = None

    for idx, file_url in enumerate(selected_files):

        # figure out the real storage key:
        if file_url.startswith('http'):
            parsed = urlparse(file_url)
            temp_key = parsed.path.lstrip('/')
        elif file_url.startswith(settings.MEDIA_URL):
            temp_key = file_url[len(settings.MEDIA_URL):]
        else:
            temp_key = file_url

        if not default_storage.exists(temp_key):
            continue

        # read & open
        with default_storage.open(temp_key, 'rb') as f:
            try:
                im = Image.open(f)
            except Exception:
                print("Error in Image.open(f)")

            # resize if needed
            if im.size != (320, 320):
                try:
                    resample = Image.Resampling.LANCZOS
                except AttributeError:
                    resample = Image.LANCZOS
                im = im.resize((320, 320), resample)

            # grayscale
            im = im.convert('L')

            # save into buffer
            buf = BytesIO()
            im.save(buf, format='PNG')
            buf.seek(0)
            im.close()

        # write back to S3
        new_filename = temp_key.rsplit('/', 1)[-1]
        dest_key = f"{user_str}/images/{new_filename}"
        default_storage.save(dest_key, ContentFile(buf.read()))
        buf.close()
        # # remove temp
        # default_storage.delete(temp_key)

        # grab this file’s DICOM metadata (or empty dict):
        mm = mri_meta_list[idx] if idx < len(mri_meta_list) else {}
        # store MRI row
        MRI.objects.create(
            filename=new_filename,
            filetype=request.POST.get('imgType', 'image/png'),
            width=320, height=320,
            user=request.user,
            path=dest_key,
            modality=mm.get('modality', ''),
            manufacturer=mm.get('manufacturer', ''),
            pixel_spacing=mm.get('pixel_spacing', ''),
            protocol_name=mm.get('protocol_name', ''),
            mri_type=mm.get('mri_type', ''),
            orientation=mm.get('orientation', ''),
            repetition_time=mm.get('repetition_time', ''),
            echo_time=mm.get('echo_time', ''),
            inversion_time=mm.get('inversion_time', ''),
            flip_angle=mm.get('flip_angle', ''),
            magnetic_field_strength=mm.get('magnetic_field_strength', ''),
            acquisition_matrix=mm.get('acquisition_matrix', ''),
            pixel_bandwidth=mm.get('pixel_bandwidth', ''),
            fov=mm.get('fov', ''),
            module=uploaded_module,
            annotator_inst=annotator_inst,
            Patient=patient_obj
        )
        # free up memory
        del im, buf
        gc.collect()

    return redirect('/')

@api_view(['GET'])
def predict_lumbar_level(request):
    """
        Given ?mri_id=123, load the MRI, run your ML model to get level,
        and return {"level": "L3-L4"}.
        """
    mri_id = request.GET.get('mri_id')
    if not mri_id:
        return Response({'error': 'mri_id required'}, status=400)

    try:
        mri = MRI.objects.get(pk=mri_id)
    except MRI.DoesNotExist:
        return Response({'error': 'not found'}, status=404)

    try:
        with default_storage.open(mri.path, 'rb') as f:
            data = f.read()
    except Exception as e:
        return Response(
            {"error": f"Could not MRI: {mri.path}: {e}"},
            status=500
        )
    # decode into a grayscale numpy array
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)


    img = img[np.newaxis, np.newaxis, ...].astype(np.float32)

    lumbar_model = load_lumbar_model()
    lumbar_model.to(device)
    lumbar_model.eval()

    inp = torch.from_numpy(img).to(device)

    with torch.no_grad():
        out = lumbar_model(inp)
    level = np.argmax(out.cpu().numpy(), axis=1)

    return Response({"level": level})


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


@api_view(['POST'])
def generate_tag(request):
    comment = request.data.get('comment', "").strip()
    level = request.data.get('level', "").strip()

    if not comment:
        return Response({"error": "No comment provided."}, status=400)

    # Build a stronger few-shot prompt
    prompt = (
        "You are a radiology tag generator. "
        "Given an optional IVD level and a clinician comment, "
        "output EXACTLY ONE TAG and nothing else, in the format:\n"
        "  <Level>: <diagnosis>\n"
        "If no level is provided, just output the diagnosis.\n\n"
        "### Example 1\n"
        "Input:\n"
        "IVD level: L5-S1\n"
        "Comment: Mild RT paracentral disc protrusion noted, abutting the thecal sac.\n"
        "Output Tag:\n"
        "L5-S1: disc protrusion\n\n"
        "### Example 2\n"
        "Input:\n"
        "Comment: Foraminal stenosis on the right side.\n"
        "Output Tag:\n"
        "foraminal stenosis\n\n"
        "### Example 3\n"
        "Input:\n"
        "IVD level: L4-L5\n"
        "Comment: Diffuse disc bulge noted.\n"
        "Output Tag:\n"
        "L4-L5: disc bulge\n\n"
        "### Now your turn\n"
        "Input:\n"
    )
    if level:
        prompt += f"IVD level: {level}\n"
    prompt += f"Comment: {comment}\n"
    prompt += "Output Tag:\n"

    tag_pipe = get_tag_pipeline()
    try:
        out = tag_pipe(
            prompt,
            max_length=16,
            num_beams=4,
            do_sample=False
        )[0]["generated_text"].strip()
        # strip any accidental prefix
        out = out.splitlines()[0]
    except Exception as e:
        return Response({"error": f"Tag generation failed: {e}"}, status=500)

    return Response({"tag": out})


@api_view(['POST'])
def compile_report(request):
    """
    Expects JSON of the form:
        { "annotations": [
            { "level": "L5-S1", "comment": "Mild RT paracentral disc protrusion …" },
            { "level": "",       "comment": "General spondylosis changes." },
            { "level": "L4-L5", "comment": "mild disc bulge noted" }
          ]
        }
    Returns:
        { "report": "<coherent radiology report>" }
    """
    data = request.data
    anns = data.get("annotations", None)
    if not isinstance(anns, list) or not anns:
        return Response({"error": "Please supply a non-empty list of {level, comment} pairs."}, status=400)

    bullet_lines = []
    for item in anns:
        lvl = (item.get("level") or "").strip()
        cmm = (item.get("comment") or "").strip()
        if not cmm:
            continue
        if lvl:
            bullet_lines.append(f"IVD level: {lvl}\nComment: {cmm}")
        else:
            bullet_lines.append(f"Comment: {cmm}")

    if not bullet_lines:
        return Response({"error": "No valid (level, comment) entries."}, status=400)

    prompt = (
            "You are a radiology assistant.  Given the following IVD‐level and comment pairs, "
            "compile them into one coherent radiology report:\n\n"
            + "\n\n".join(bullet_lines)
            + "\n\nReport:"
    )

    tag_pipe = get_tag_pipeline()
    try:
        outputs = tag_pipe(prompt, max_length=512, do_sample=False)
        raw = outputs[0]["generated_text"].strip()
    except Exception as e:
        return Response({"error": f"Tag-pipeline failed: {str(e)}"}, status=500)

    return Response({"report": raw})

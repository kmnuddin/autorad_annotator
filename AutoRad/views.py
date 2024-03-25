import numpy as np
from django.shortcuts import render
from django.core.files.storage import FileSystemStorage
from urllib.parse import unquote
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.http import JsonResponse
import cv2
import torch
from .model import model, device
import matplotlib.pyplot as plt
from django.conf import settings
import os


def home(request):
    return render(request, 'home.html')

def upload_image(request):
    context = {}
    if request.method == 'POST' and request.FILES['image']:
        image = request.FILES['image']
        fs = FileSystemStorage()
        filename = fs.save(image.name, image)
        image_url = fs.url(filename)
        context['image_url'] = image_url

    return render(request, 'home.html', context)


@api_view(['POST'])
def view_mask(request):
    mask_path = request.data.get('mask_url')
    filename = unquote(mask_path).split('/')[-1]
    mask_load_path = os.path.join(settings.MEDIA_ROOT, filename)
    mask = np.load(mask_load_path)

    full_mask = np.squeeze(np.argmax(mask, axis=1))
    mask_img_filename = filename.split('.')[0] + '.png'
    mask_save_path = os.path.join(settings.MEDIA_ROOT, mask_img_filename)
    plt.imsave(mask_save_path, full_mask, cmap='gray')
    fs = FileSystemStorage()

    full_mask_url = fs.url(mask_img_filename)
    mask_class_paths = []
    classes = ["IVD", "PE", "TS", "AAP"]
    for i in range(1, mask.shape[1]):
        class_fname = filename.split('.')[0]+ '_' + classes[i-1] + '.png'
        class_save_path = os.path.join(settings.MEDIA_ROOT, class_fname)
        plt.imsave(class_save_path, np.squeeze(mask)[i], cmap='gray')
        mask_class_url = fs.url(class_fname)
        mask_class_paths.append(mask_class_url)


    return Response({'mask_url': full_mask_url, 'mask_class_paths': mask_class_paths})

@api_view(['POST'])
def get_control_points(request):
    mask_path = request.data.get('mask_url')
    filename = unquote(mask_path).split('/')[-1]
    filename = filename.split('.')[0]
    mask_paths = []
    classes = ["IVD", "PE", "TS", "AAP"]
    structure_cnt_points = {}
    for cls in classes:
        filename_cls = filename + '_' + cls + '.png'
        mask_cls_path = os.path.join(settings.MEDIA_ROOT, filename_cls)

        mask = cv2.imread(mask_cls_path, cv2.IMREAD_GRAYSCALE)
        cnts, hier = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        cnts = sorted(cnts, key=cv2.contourArea)
        structure_cnt_points[cls] = [cnt.tolist() for cnt in cnts]


    return JsonResponse({'cls_cnt': structure_cnt_points})


@api_view(['POST'])
def process_image(request):
    if request.method == 'POST' and request.FILES['image']:
        # Save image
        image = request.FILES['image']
        fs = FileSystemStorage()
        filename = fs.save(image.name, image)
        image_path = fs.path(filename)

        img_mat = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)[np.newaxis, ...].astype(np.float32)
        img_mat = img_mat[np.newaxis, ...]

        with torch.no_grad():
            img_mat = torch.from_numpy(img_mat)
            img_mat = img_mat.to(device)
            mask = model(img_mat)

        # mask = torch.squeeze(torch.argmax(mask, dim=1))
        mask_np = mask.cpu().numpy()  # Convert the tensor to a numpy array
        # mask_np = mask_np.astype(np.uint8)  # Ensure it's in 'uint8' format for image saving
        # mask_np = lbl_decoder(mask_np)
        mask_filename = 'mask_' + filename.split('.')[0] + '.npy'
        mask_file_path = os.path.join(settings.MEDIA_ROOT, mask_filename)
        np.save(mask_file_path, mask_np)  # Save as .npy

        # Get the URL for the saved mask
        mask_url = fs.url(mask_filename)

        return Response({'mask_url': mask_url})
    return Response({'error': 'No image provided'}, status=400)







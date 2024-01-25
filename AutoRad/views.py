import numpy as np
from django.shortcuts import render
from django.core.files.storage import FileSystemStorage

from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.core.files.base import ContentFile
import cv2
from PIL import Image
import torch
from .model import model, device
import matplotlib.pyplot as plt
from django.conf import settings
from django.utils.crypto import get_random_string
from io import BytesIO
import os
import base64

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

        mask = torch.squeeze(torch.argmax(mask, dim=1))
        mask_np = mask.cpu().numpy()  # Convert the tensor to a numpy array
        mask_np = mask_np.astype(np.uint8)  # Ensure it's in 'uint8' format for image saving
        # mask_np = lbl_decoder(mask_np)

        mask_filename = 'mask_' + filename
        mask_file_path = os.path.join(settings.MEDIA_ROOT, mask_filename)
        plt.imsave(mask_file_path, mask_np, cmap='gray')  # Save as grayscale

        # Get the URL for the saved mask
        mask_url = fs.url(mask_filename)

        return Response({'mask_url': mask_url})
    return Response({'error': 'No image provided'}, status=400)

def blend_image_with_mask(image, mask):
    cmap = plt.cm.get_cmap('tab20b', 5)  # Get a colormap with 5 colors
    colors = [cmap(i) for i in range(5)]

    # Convert RGB values to 8-bit for visualization
    colors = (np.array(colors)[:, :3] * 255).astype(np.uint8)

    alpha = 0.6


    # Create a blank RGB image with the same dimensions as the original image
    color_mask = np.zeros_like(image)

    for label, color in enumerate(colors):
        color_mask[mask == label] = color

    blended = cv2.addWeighted(image, alpha, color_mask, 1 - alpha, 0)

    # Ensure values are within the expected range
    blended = np.clip(blended, 0, 255)
    return blended / 255.0

@api_view(['POST'])
def show_blended_mri(request):
    image_data = request.data.get('image_url')
    mask_path = request.data.get('mask_url')

    if not image_data or not mask_path:
        return Response({'error': 'Image data and/or mask path not provided'}, status=400)

    # Decode the base64 image data
    image_base64 = image_data.split(',')[1]
    image_bytes = base64.b64decode(image_base64)
    image = np.array(Image.open(BytesIO(image_bytes)))

    # Read the mask file from the server
    full_mask_path = os.path.join(settings.MEDIA_ROOT, mask_path.lstrip('/'))
    mask = np.array(Image.open(mask_path))

    # Process the image and mask
    blended_image = blend_image_with_mask(image, mask)

    # Convert the blended image to an in-memory file
    pil_img = Image.fromarray((blended_image * 255).astype(np.uint8))
    image_io = BytesIO()
    pil_img.save(image_io, format='PNG')
    image_io.seek(0)

    # Save the in-memory file using Django's file storage system
    unique_id = get_random_string(length=10)
    filename = 'blended_{}_{}'.format(unique_id, os.path.basename(mask_path))
    fs = FileSystemStorage()
    image_path = fs.save(filename, ContentFile(image_io.read()))
    image_url = fs.url(image_path)

    return Response({'image_url': image_url})



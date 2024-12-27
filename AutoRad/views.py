import numpy as np
from django.shortcuts import render,redirect
from django.core.files.storage import FileSystemStorage
from django.contrib.auth.forms import UserCreationForm
from django.views.generic.edit import CreateView
from django.urls import reverse_lazy
from django.contrib.auth import login
from urllib.parse import unquote
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.http import JsonResponse
import cv2
import torch
from .utils import model, device
import matplotlib.pyplot as plt
from django.conf import settings
import os
import logging
import json
from django.contrib import messages
from django.http import HttpResponse

# import customized class models
from .models import patientClass,reportClass,imgClass,maskClass

from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt

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
### When homepage is loading, it will pull all the image under the current user from DB.
def home(request):
    images = imgClass.objects.filter(userAcc = request.user)
    # print(images)
    context = {'images':images}
    # print(context)
    return render(request,'home.html',context)
    # return render(request, 'home.html')

logger = logging.getLogger(__name__)

### Used to analysis each mask and do separation and save sigmentations' information to the mask.
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
        tempMask = maskClass.objects.get(maskName = filename_cls)
        mask_cls_path = os.path.join(settings.MEDIA_ROOT, filename_cls)

        mask = cv2.imread(mask_cls_path, cv2.IMREAD_GRAYSCALE)
        mask = cv2.resize(mask, (500, 500))
        cnts, hier = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        cnts = sorted(cnts, key=cv2.contourArea)
        print(cls,"'s length: ", len(cnts))
        structure_cnt_points[cls] = [cnt.tolist() for cnt in cnts]        
        tempMask.maskPts = structure_cnt_points[cls]
        tempMask.save()

    return JsonResponse({'cls_cnt': structure_cnt_points})


### Used to save image, and Masks to DB
@api_view(['POST','GET'])
def save_image(request):
    if request.method == 'POST':
        imageDB = imgClass()
        if len(request.FILES) !=0:
            imageDB.imgFile = request.FILES['image']
        imageDB.imgName = request.POST.get('imgName')
        imageDB.type = request.POST.get('imgType')
        imageDB.width = request.POST.get('imgWidth')
        imageDB.height = request.POST.get('imgHeight')
        imageDB.userAcc = request.user
        
        imageDB.save()

        try:
            image_path = r'.' + imageDB.imgFile.url
            filename = imageDB.imgFile.name
            img_mat = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)[np.newaxis, ...].astype(np.float32)
            img_mat = img_mat[np.newaxis, ...]
            
            with torch.no_grad():
                img_mat = torch.from_numpy(img_mat)
                img_mat = img_mat.to(device)
                mask = model(img_mat)
                
            mask_np = mask.cpu().numpy()
            
            full_mask = np.squeeze(np.argmax(mask_np, axis=1))
            
            mask_img_filename = filename.split('.')[0] + '.jpg'
            mask_save_path = os.path.join(settings.MEDIA_ROOT, mask_img_filename)
            plt.imsave(mask_save_path, full_mask, cmap='gray')  # Save as .jpg， will not be recorded in DB.
            
            classes = ["IVD", "PE", "TS", "AAP"]
            for i in range(1, mask_np.shape[1]):
                
                cls=classes[i-1]
                
                class_fname = filename.split('.')[0]+ '_' + cls + '.png'
                class_save_path = os.path.join(settings.MEDIA_ROOT, class_fname)
                plt.imsave(class_save_path, np.squeeze(mask)[i], cmap='gray')
                
                ### Save mask information in diff categories
                tempMask = maskClass()
                tempMask.maskName = class_fname
                tempMask.maskType = cls
                tempMask.maskFile = class_fname                
                tempMask.imgID = imageDB
                
                tempMask.save()                
        except Exception as e:
            print("Error! ",e)
        
        messages.success(request,"image upload successfully!")
        return redirect('/')
    return render(request, 'saveImg.html')


### this is the placeholder for remove an image. It will redirect to delImg.html
@api_view(['GET'])
def del_image(request,imgId):
    image = imgClass.objects.filter(id=imgId)
    masks = maskClass.objects.filter(imgID=imgId)
    image.delete()
    masks.delete()
    messages.success(request,"Image and related masks are successfully deleted!")
    return redirect('/')
    
    
### ====================================
### Function unused below
### ====================================

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

@api_view(['POST'])
def view_mask(request):

    print('called view_mask')
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

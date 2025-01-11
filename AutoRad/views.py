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

# ===============================
# import customized class models
from .models import imgClass,maskClass,patternClass
# ===============================

from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt

# Sign up
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

### When homepage is loading, it will pull all the image satisfying the filters from DB.
#   under the current user OR
#   under certain Project (need code changing on model to include the new field)
#   To do:
#   1. Model.py to include the new field project
#   2. After 1, change the filter to filtered by project selected
#   3. On saveImg.html, have the project input field. Have some default value.
@login_required
def home(request):
    images = imgClass.objects.filter(userAcc = request.user)
    # print(images)
    context = {'images':images}
    # print(context)
    return render(request,'home.html',context)
    # return render(request, 'home.html')


### Used to analysis each mask and do separation and save sigmentations' information to the mask.
# to do: 
# 1. try to remove mask file
# 2. rename the function
# 3. fix the coordinates' issue
@api_view(['POST'])
def get_control_points(request):
    mask_path = request.data.get('mask_url')
    img_ID = request.data.get('imgID')
    filename = unquote(mask_path).split('/')[-1]
    filename = filename.split('.')[0]
    classes = ["IVD", "PE", "TS", "AAP"]
    structure_cnt_points = {}
    for cls in classes:
        filename_cls = filename + '_' + cls + '.png'
        tempMask = maskClass.objects.get(maskType = cls, imgID=img_ID)
        mask_cls_path = os.path.join(settings.MEDIA_ROOT, filename_cls)
        # if (tempMask.maskPts != ""):
        #     print("Segimentation has already been done!")
        #     structure_cnt_points[cls] = eval(tempMask.maskPts) ## Due to field is a string. Need to convert it into desired format[{x:1,y:2},{...}]
        # else:
        mask = cv2.imread(mask_cls_path, cv2.IMREAD_GRAYSCALE)
        # mask = cv2.resize(mask, (500, 500))
        cnts, hier = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        cnts = sorted(cnts, key=cv2.contourArea)
        print(cls,"'s length: ", len(cnts))
        # print(hier)
        temp = [cnt.tolist() for cnt in cnts]
        structure_cnt_points[cls]=[]
        GminX = 500
        GminY = 500
        for pattern in temp:
            # print("Patterns: ",pattern)
            # structure_cnt_points[cls]
            pnt_list = [dict(zip(["x","y"], pnt[0])) for pnt in pattern ]
            # print(pnt_list)
            LminX = 500
            LminY = 500
            
            for pnt in pnt_list:
                # print(pnt)
                if GminX > pnt['x']:
                    GminX = pnt['x']
                if GminY > pnt['y']:
                    GminY = pnt['y']
                if LminX > pnt['x']:
                    LminX = pnt['x']
                if LminY > pnt['y']:
                    LminY = pnt['y']
            print(LminY," ",LminX)
            # print("Pattern: ",pnt_list)
            structure_cnt_points[cls].append(pnt_list)
            
            name = cls + "_" + str(int(temp.index(pattern)) + 1)
            patternsExisted = patternClass.objects.filter(patternName = name, maskID = tempMask.id)
            if (len(patternsExisted)==0):
                tempPattern = patternClass()
                tempPattern.patternName = name
                tempPattern.patternType = cls
                tempPattern.patternPts = pnt_list
                tempPattern.patternTop = LminY
                tempPattern.patternLeft = LminX
                tempPattern.maskID = tempMask
                
                tempPattern.save()
                # print(tempPattern)
            else:
                print("Pattern ",name," existed!")
            
        # print("Top: ",GmaxY)
        # print("Left: ",GminX)
        tempMask.maskTop = GminY
        tempMask.maskLeft = GminX  
        tempMask.maskPts = structure_cnt_points[cls]
        # print(tempMask.maskPts)
        tempMask.save()

    return JsonResponse({'cls_cnt': structure_cnt_points})


### Used to save image, and Masks to DB
# to do: 
# 1. Add project field.
# 2. remove mask image if possible.
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
            plt.imsave(mask_save_path, full_mask, cmap='gray')  # Save as .jpg， will not be recorded in DB, or do we need it?
            
            classes = ["IVD", "PE", "TS", "AAP"]
            for i in range(1, mask_np.shape[1]):
                
                cls=classes[i-1]
                
                class_fname = filename.split('.')[0]+ '_' + cls + '.png'
                class_save_path = os.path.join(settings.MEDIA_ROOT, class_fname)
                plt.imsave(class_save_path, np.squeeze(mask_np)[i], cmap='gray')
                
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
### Need some work on deletion confirmation.
@api_view(['GET'])
def del_image(request,imgId):
    image = imgClass.objects.filter(id=imgId)
    masks = maskClass.objects.filter(imgID=imgId)
    
    masks.delete()
    image.delete()
    
    messages.success(request,"Image and related masks are successfully deleted!")
    return redirect('/')
    
### Function to query the Sqlite3 DB for information
@api_view(['POST'])
def obtainInfo(request):
    jobs = request.data
    print(jobs)
    objType = request.data.get('objType')
    objID = int(request.data.get('objID'))
    outputJSON = {}
    
    if (objType == "image"):
        object = imgClass.objects.get(id = objID)
        outputJSON = {
            'imgName':object.imgName,
            'width':object.width,
            'height':object.height,
            'type': object.type,
            'created_at': object.created_at,
            'modified_at': object.modified_at
        }
        print("==================================")
        print(objType, " Query DB Successfully!")
        print("==================================")
        return JsonResponse({'image': outputJSON})
    if (objType == "images"):
        objects = imgClass.objects.filter(userAcc = objID)
    if (objType == "mask"):
        objCategory = request.data.get('objCategory')
        objects = maskClass.objects.get(imgID = objID,maskType = objCategory)
        
    if (objType == "masks"):
        objects = maskClass.objects.filter(imgID = objID)        
        for item in objects:
            outputJSON[item.maskType] = {
                'maskID':item.id,
                'maskName':item.maskName,
                'maskType':item.maskType,
                # 'maskFile':item.maskFile, //Image field, can't be used as json response
                'maskPts':item.maskPts,
                'maskTop':item.maskTop,
                'maskLeft':item.maskLeft,
                'maskAngle':item.maskAngle,
                'maskScale':item.maskScale,
                'maskOpacity':item.maskOpacity,
                'maskCornerColor':item.maskCornerColor,
                'maskStrokeColor':item.maskStrokeColor
                }
        print("==================================")
        print(objType, " Query DB Successfully!")
        print("==================================")
        # print(objType,": ",outputJSON)
        
        return JsonResponse({'masks': outputJSON})
    
    if (objType == "pattern"):
        objCategory = request.data.get('objCategory')
        objName = request.data.get('objName')
        mask = maskClass.objects.get(imgID = objID,maskType = objCategory)
        pattern = patternClass.objects.get(maskID = mask.id, patternName = objName)
        
        outputJSON[pattern.patternName] = {
            'patternName': pattern.patternName,
            'patternType': pattern.patternType,
            'patternPts': pattern.patternPts,
            'patternTop':pattern.patternTop,
            'patternLeft':pattern.patternLeft,
            'patternAngle':pattern.patternAngle,
            'patternScale':pattern.patternScale,
            'patternOpacity':pattern.patternOpacity,
            'patternCornerColor':pattern.patternCornerColor,
            'patternStrokeColor':pattern.patternStrokeColor
        }
        print("==================================")
        print(objType, " Query DB Successfully!")
        print("==================================")
        return JsonResponse({'pattern': outputJSON})
    
    if (objType == "patterns"): # Query all patterns for an image.
        masks = maskClass.objects.filter(imgID = objID)
        for mask in masks:
            patterns = patternClass.objects.filter(maskID = mask.id)
            for pattern in patterns:
                outputJSON[pattern.patternName] = {
                    'patternName': pattern.patternName,
                    'patternType': pattern.patternType,
                    'patternPts': pattern.patternPts,
                    'patternTop':pattern.patternTop,
                    'patternLeft':pattern.patternLeft,
                    'patternAngle':pattern.patternAngle,
                    'patternScale':pattern.patternScale,
                    'patternOpacity':pattern.patternOpacity,
                    'patternCornerColor':pattern.patternCornerColor,
                    'patternStrokeColor':pattern.patternStrokeColor
                }
        print("==================================")
        print(objType, " Query DB Successfully!")
        print("==================================")
        return JsonResponse({'patterns': outputJSON})
    
    print("Query DB Unsuccessfully!")
    print("==================================")
    print(objType," : ",objID)
    print("==================================")
    return Response({'error':'Invild input provided!'}, status=400)

### Function to update the Sqlite3 DB for information
@api_view(['POST'])
def updateInfo(request):
    objType = request.data.get('objType')
    objID = int(request.data.get('objID'))
    objCategory = request.data.get('maskType')
    newMask = dict(request.data.get('mask'))
    print(newMask)
    print(type(newMask))
    # outputJSON = {}
    
    if (objType == "image"):
        image = imgClass.objects.get(id = objID)
    
    if (objType == "mask"):
        
        mask = maskClass.objects.get(imgID = objID, maskType = objCategory)        
        mask.maskPts = newMask['maskPts']
        mask.maskTop = newMask['maskTop']
        mask.maskLeft = newMask['maskLeft']
        mask.maskAngle = newMask['maskAngle']
        mask.maskScale = newMask['maskScale']
        mask.maskOpacity = newMask['maskOpacity']
        mask.maskCornerColor = newMask['maskCornerColor']
        mask.maskStrokeColor = newMask['maskStrokeColor']

        mask.save()
        
        print("==================================")
        print("DB updated Successfully!")
        print("==================================")
        
        return Response({'Message':'Mask is updated successfully!'}, status=200)
    
    print("Query DB Unsuccessfully!")
    print("==================================")
    print(objType," : ",objID)
    print("==================================")
    return Response({'error':'Invild input provided!'}, status=400)

### ====================================
### Function unused below
### ====================================

# logger = logging.getLogger(__name__)

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

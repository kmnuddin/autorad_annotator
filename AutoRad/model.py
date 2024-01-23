from django.conf import settings
import os
import torch

model = None

def load_model():
    global model
    model_path = os.path.join(settings.BASE_DIR, 'AutoRad', 'DL Model', 'best_unet.pth')
    model = torch.load(model_path)
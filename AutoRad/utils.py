from django.conf import settings

import os
import torch
import torch.nn as nn

model = None
device = 'cuda' if torch.cuda.is_available() else 'cpu'
def load_model():
    global model
    global device

    model = torch.hub.load('mateuszbuda/brain-segmentation-pytorch', 'unet',
                           in_channels=1, out_channels=1, init_features=32, pretrained=False)

    model.conv = nn.Conv2d(32, 5, kernel_size=1, stride=1)

    model_path = os.path.join(settings.BASE_DIR, 'AutoRad', 'DL Model', 'best_unet.pth')


    state_dict = torch.load(model_path)

    model.load_state_dict(state_dict)
    model.to(device)

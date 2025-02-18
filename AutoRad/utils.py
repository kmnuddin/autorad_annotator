from django.conf import settings

import io
import os
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import pydicom
from PIL import Image

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


def one_hot_encode_masks(masks_numpy):
    """
    Converts a NumPy array of segmentation masks to a one-hot encoded PyTorch tensor.
    Each unique mask value is remapped to [0..(num_classes-1)] before one-hot encoding.

    :param masks_numpy: NumPy array of shape (height, width) or (batch, height, width)
                        containing segmentation masks with integer labels.
    :return: One-hot encoded PyTorch tensor of shape (batch_size, num_classes, height, width).
    """
    # 1) Figure out the unique values in the mask. E.g. [0, 64, 128, 192, 255]
    unique_labels = np.unique(masks_numpy)
    num_classes = len(unique_labels)

    # 2) Build a dictionary mapping each raw label to an index in [0..num_classes-1]
    #    e.g. {0:0, 64:1, 128:2, 192:3, 255:4}
    label_to_index = {val: idx for idx, val in enumerate(unique_labels)}

    # 3) Use NumPy's vectorize or a direct approach to remap the entire mask array
    #    from the raw label to [0..num_classes-1]
    remapped = np.vectorize(label_to_index.get)(masks_numpy)

    # 4) Convert the remapped array to a long tensor for F.one_hot.
    #    If your 'masks_numpy' was (height, width), add a batch dimension.
    if remapped.ndim == 2:
        # shape -> (1, height, width)
        remapped = remapped[np.newaxis, ...]

    # If it's already (batch, height, width), we're good
    masks_tensor = torch.from_numpy(remapped).long()

    # 5) One-hot encode: shape becomes (batch, height, width, num_classes)
    one_hot = F.one_hot(masks_tensor, num_classes=num_classes).float()

    # Rearrange to (batch, num_classes, height, width)
    one_hot = one_hot.permute(0, 3, 1, 2)

    return one_hot.numpy()

def dicom_to_png(file_obj, output_path):
    """
    Convert a DICOM/IMA file (from a file-like object) to a PNG image
    and save it to output_path.
    """
    # Read the entire file into memory
    file_bytes = file_obj.read()
    # Wrap bytes in a BytesIO stream so pydicom can read it.
    f = io.BytesIO(file_bytes)
    # Read the DICOM dataset.
    ds = pydicom.dcmread(f)
    # Extract pixel array from the dataset.
    arr = ds.pixel_array

    # Normalize the array to the 0-255 range.
    arr = arr.astype(np.float32)
    min_val = np.min(arr)
    max_val = np.max(arr)
    if max_val - min_val > 0:
        arr = ((arr - min_val) / (max_val - min_val)) * 255.0
    arr = arr.astype(np.uint8)

    # If the DICOM file has multiple frames, take the first frame.
    if arr.ndim > 2:
        arr = arr[0]

    # Convert the numpy array to a PIL Image.
    img = Image.fromarray(arr)
    # Save the image as a PNG.
    img.save(output_path, format='PNG')
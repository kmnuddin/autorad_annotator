from django.conf import settings

from functools import lru_cache
import io
import os
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np

import torch
from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM

from PIL import Image
from .dl.unet import UNet
from io import BytesIO

model = None
device = 'cuda' if torch.cuda.is_available() else 'cpu'


def load_model():
    global model
    global device

    # 1) Instantiate your local UNet
    model = UNet(in_channels=1, out_channels=1, init_features=32)

    # 2) Swap in your custom final conv for 5‐class output
    model.conv = nn.Conv2d(32, 5, kernel_size=1, stride=1)

    model_path = os.path.join(settings.BASE_DIR, 'AutoRad', 'dl', 'best_unet.pth')

    state_dict = torch.load(model_path, map_location=torch.device('cpu'))

    model.load_state_dict(state_dict)
    model.to(device)


@lru_cache(maxsize=1)
def get_tag_pipeline():
    """
    Lazily loads and caches a FLAN-T5-small text2text-generation pipeline on CPU.
    """
    MODEL_ID = "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B"
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
    lm = AutoModelForCausalLM.from_pretrained(MODEL_ID, trust_remote_code=True)
    # ensure it stays on CPU
    lm.to("cpu")

    return pipeline(
        "text-generation",
        model=lm,
        tokenizer=tokenizer,
        device=-1,  # -1 means CPU
        return_full_text=False,  # only return the newly generated tokens
        do_sample=False,  # deterministic output
        max_new_tokens=32
    )


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


# def dicom_to_png(file_obj, output_path):
#     """
#     Convert a DICOM/IMA file (from a file-like object) to a PNG image
#     and save it to output_path.
#     """
#     # Read the entire file into memory
#     file_bytes = file_obj.read()
#     # Wrap bytes in a BytesIO stream so pydicom can read it.
#     f = io.BytesIO(file_bytes)
#     # Read the DICOM dataset.
#     ds = pydicom.dcmread(f)
#     # Extract pixel array from the dataset.
#     arr = ds.pixel_array
#
#     # Normalize the array to the 0-255 range.
#     arr = arr.astype(np.float32)
#     min_val = np.min(arr)
#     max_val = np.max(arr)
#     if max_val - min_val > 0:
#         arr = ((arr - min_val) / (max_val - min_val)) * 255.0
#     arr = arr.astype(np.uint8)
#
#     # If the DICOM file has multiple frames, take the first frame.
#     if arr.ndim > 2:
#         arr = arr[0]
#
#     # Convert the numpy array to a PIL Image.
#     img = Image.fromarray(arr)
#     # Save the image as a PNG.
#     img.save(output_path, format='PNG')
#
#     return ds

def dicom_to_png_bytes(ds):
    """
    Given a pydicom Dataset, return a PNG as bytes and the Dataset itself.
    """
    arr = ds.pixel_array.astype(np.float32)
    mn, mx = arr.min(), arr.max()
    if mx > mn:
        arr = ((arr - mn) / (mx - mn) * 255.0).astype(np.uint8)
    if arr.ndim > 2:
        arr = arr[0]
    img = Image.fromarray(arr)
    buf = BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf.read(), ds


def get_mri_type(ds):
    """
    Extract the MRI type (e.g., 'T1' or 'T2') from a pydicom Dataset.
    Checks the following tags in order:
      1. ImageType (0008,0008)
      2. SequenceName (0018,0024)
      3. ScanningSequence (0018,0020)
      4. SeriesDescription (0008,103E)
    Returns:
        str: 'T1' or 'T2' if detected; otherwise, "N/A".
    """
    image_type = getattr(ds, 'ImageType', None)
    if image_type:
        # If it's a string, split it on backslashes.
        if isinstance(image_type, str):
            components = image_type.split('\\')
        else:
            # Otherwise, assume it's iterable and convert each element to a string.
            components = [str(comp) for comp in image_type]
        for comp in components:
            comp = comp.upper()
            if 'T1' in comp:
                return 'T1'
            elif 'T2' in comp:
                return 'T2'

    # 2. Fallback: Check SequenceName
    sequence_name = getattr(ds, 'SequenceName', None)
    if sequence_name:
        seq = sequence_name.upper() if isinstance(sequence_name, str) else str(sequence_name).upper()
        if 'T1' in seq:
            return 'T1'
        elif 'T2' in seq:
            return 'T2'

    # 3. Additional fallback: Check ScanningSequence
    scanning_seq = getattr(ds, 'ScanningSequence', None)
    if scanning_seq:
        scan = scanning_seq.upper() if isinstance(scanning_seq, str) else str(scanning_seq).upper()
        if 'T1' in scan:
            return 'T1'
        elif 'T2' in scan:
            return 'T2'

    # 4. Additional fallback: Check SeriesDescription
    series_description = getattr(ds, 'SeriesDescription', None)
    if series_description:
        sd = series_description.upper() if isinstance(series_description, str) else str(series_description).upper()
        if 'T1' in sd:
            return 'T1'
        elif 'T2' in sd:
            return 'T2'

    return "N/A"


def get_orientation(ds):
    """
    Determine the orientation (axial, sagittal, or coronal) from a pydicom Dataset.

    Uses the ImageOrientationPatient (0020,0037) tag, which is a list of six values:
      [r1, r2, r3, c1, c2, c3]
    where the first three values represent the direction cosines of the image's rows,
    and the last three represent the direction cosines of the columns.

    Heuristic:
      - Axial: the dominant row direction is along the x-axis (index 0) and the dominant column direction is along the y-axis (index 1).
      - Sagittal: the dominant row direction is along the y-axis (index 1) and the dominant column is along the z-axis (index 2).
      - Coronal: the dominant row direction is along the x-axis (index 0) and the dominant column is along the z-axis (index 2).

    If the tag is missing or ambiguous, it falls back on PatientPosition.

    Returns:
      A string: "axial", "sagittal", "coronal", or an empty string if not determined.
    """
    iop = getattr(ds, "ImageOrientationPatient", None)
    if iop and len(iop) >= 6:
        try:
            # Ensure the values are floats.
            iop = [float(x) for x in iop]
        except Exception:
            return ""

        # First three values are row direction, next three are column direction.
        row = iop[:3]
        col = iop[3:6]

        # Use absolute values to determine the dominant direction.
        abs_row = [abs(x) for x in row]
        abs_col = [abs(x) for x in col]

        dominant_row = abs_row.index(max(abs_row))
        dominant_col = abs_col.index(max(abs_col))

        # Heuristic rules:
        # Axial: dominant row is 0 (x-direction), dominant column is 1 (y-direction)
        if dominant_row == 0 and dominant_col == 1:
            return "axial"
        # Sagittal: dominant row is 1 (y-direction), dominant column is 2 (z-direction)
        elif dominant_row == 1 and dominant_col == 2:
            return "sagittal"
        # Coronal: dominant row is 0 (x-direction), dominant column is 2 (z-direction)
        elif dominant_row == 0 and dominant_col == 2:
            return "coronal"
        else:
            # If the heuristic doesn't match clearly, return an empty string.
            return "N/A"
    else:
        # Fallback: use PatientPosition if available.
        patient_pos = getattr(ds, "PatientPosition", "").upper()
        if patient_pos in ["HFS", "FFS"]:
            return "axial"
        return "N/A"


def extract_patient_metadata(ds):
    """
    Extract patient metadata from a pydicom Dataset.
    Returns a dictionary with keys: patient_id, age, weight, height, sex.
    """
    metadata = {'patient_id': str(getattr(ds, 'PatientID', '')), 'age': str(getattr(ds, 'PatientAge', '')),
                'weight': str(getattr(ds, 'PatientWeight', '')), 'height': str(getattr(ds, 'PatientSize', '')),
                'sex': str(getattr(ds, 'PatientSex', ''))}
    return metadata


def extract_mri_metadata(ds):
    """
    Extract MRI acquisition metadata from a pydicom Dataset.
    Returns a dictionary containing modality, manufacturer, pixel_spacing, protocol_name,
    repetition_time, echo_time, inversion_time, flip_angle, magnetic_field_strength,
    acquisition_matrix, pixel_bandwidth, fov, series_description, mri_type, orientation.
    """
    metadata = {'modality': str(getattr(ds, 'Modality', '')), 'manufacturer': str(getattr(ds, 'Manufacturer', ''))}

    # PixelSpacing may be a list of values.
    pixel_spacing = getattr(ds, 'PixelSpacing', None)
    if pixel_spacing:
        metadata['pixel_spacing'] = " x ".join([str(x) for x in pixel_spacing])
    else:
        metadata['pixel_spacing'] = ""

    metadata['protocol_name'] = str(getattr(ds, 'ProtocolName', ''))
    metadata['repetition_time'] = str(getattr(ds, 'RepetitionTime', ''))
    metadata['echo_time'] = str(getattr(ds, 'EchoTime', ''))
    metadata['inversion_time'] = str(getattr(ds, 'InversionTime', ''))
    metadata['flip_angle'] = str(getattr(ds, 'FlipAngle', ''))
    metadata['magnetic_field_strength'] = str(getattr(ds, 'MagneticFieldStrength', ''))

    acq_matrix = getattr(ds, 'AcquisitionMatrix', None)
    if acq_matrix:
        metadata['acquisition_matrix'] = "x".join([str(x) for x in acq_matrix])
    else:
        metadata['acquisition_matrix'] = ""

    metadata['pixel_bandwidth'] = str(getattr(ds, 'PixelBandwidth', ''))

    # FOV might be stored in different tags.
    fov = getattr(ds, 'AcquisitionFieldOfViewDimensions', None) or getattr(ds, 'FieldOfView', '')
    if isinstance(fov, (list, tuple)):
        metadata['fov'] = " x ".join([str(x) for x in fov])
    else:
        metadata['fov'] = str(fov)

    metadata['series_description'] = str(getattr(ds, 'SeriesDescription', ''))

    # Use our utility functions for MRI type and orientation.
    metadata['mri_type'] = get_mri_type(ds)
    metadata['orientation'] = get_orientation(ds)

    return metadata

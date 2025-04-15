import os
import json
from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser

# Determine the directory containing this file.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Build the path to institutions.json
institutions_file = os.path.join(BASE_DIR, 'institutions.json')

# Load the institutions list from the JSON file.
with open(institutions_file, 'r') as f:
    institution_list = json.load(f)

# Create choices as a list of tuples (value, display)
INSTITUTION_CHOICES = [(inst, inst) for inst in institution_list]


class CustomUserCreationForm(UserCreationForm):
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    email = forms.EmailField(max_length=254, required=True)
    institution = forms.ChoiceField(choices=INSTITUTION_CHOICES, required=True)

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ('username', 'first_name', 'last_name', 'email', 'institution')

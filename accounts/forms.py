from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User

class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    phone_number = forms.CharField(max_length=20, required=False)
    whatsapp_number = forms.CharField(max_length=20, required=False)
    
    class Meta:
        model = User
        fields = ('username', 'email', 'phone_number', 'whatsapp_number', 'password1', 'password2')

class OrganizationRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    phone_number = forms.CharField(max_length=20, required=False)
    whatsapp_number = forms.CharField(max_length=20, required=False)
    
    class Meta:
        model = User
        fields = ('username', 'email', 'phone_number', 'whatsapp_number', 'password1', 'password2')
        
    def save(self, commit=True):
        user = super().save(commit=False)
        user.user_type = 'organization'
        if commit:
            user.save()
        return user
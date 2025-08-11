from django import forms
from .models import Organization, AnonymousSubscription


class OrganizationForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = [
            'name', 'description', 'website', 'logo', 'notification_type',
            'smtp_host', 'smtp_port', 'smtp_username', 'smtp_password',
            'twilio_account_sid', 'twilio_auth_token', 'twilio_phone_number', 'twilio_whatsapp_number'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'smtp_password': forms.PasswordInput(),
            'twilio_auth_token': forms.PasswordInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['smtp_host'].widget.attrs.update({'placeholder': 'smtp.gmail.com'})
        self.fields['smtp_port'].widget.attrs.update({'placeholder': '587'})


class AnonymousSubscriptionForm(forms.ModelForm):
    class Meta:
        model = AnonymousSubscription
        fields = ['name', 'email', 'phone_number', 'whatsapp_number', 'notification_preference']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Your full name'}),
            'email': forms.EmailInput(attrs={'placeholder': 'your@email.com'}),
            'phone_number': forms.TextInput(attrs={'placeholder': '+1234567890 (optional)'}),
            'whatsapp_number': forms.TextInput(attrs={'placeholder': '+1234567890 (optional)'}),
        }
from django import forms
from .models import Organization, Subscription, AnonymousSubscription


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
        # Make API fields conditional based on notification type
        self.fields['smtp_host'].required = False
        self.fields['smtp_port'].required = False
        self.fields['smtp_username'].required = False
        self.fields['smtp_password'].required = False
        self.fields['twilio_account_sid'].required = False
        self.fields['twilio_auth_token'].required = False
        self.fields['twilio_phone_number'].required = False
        self.fields['twilio_whatsapp_number'].required = False


class SubscriptionForm(forms.ModelForm):
    class Meta:
        model = Subscription
        fields = ['notification_preference']
        widgets = {
            'notification_preference': forms.RadioSelect(),
        }


class AnonymousSubscriptionForm(forms.ModelForm):
    class Meta:
        model = AnonymousSubscription
        fields = ['name', 'email', 'phone_number', 'whatsapp_number', 'notification_preference']
        widgets = {
            'notification_preference': forms.RadioSelect(),
        }

    def clean_email(self):
        email = self.cleaned_data['email']
        # Basic email validation is handled by EmailField
        return email.lower().strip()

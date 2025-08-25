from django import forms
from hcaptcha.fields import hCaptchaField
from .models import Organization, Subscription, AnonymousSubscription, NotificationPreference


class OrganizationForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = [
            'name',
            'description',
            'website',
            'logo',
            'contact_email',
            'contact_phone',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }


class NotificationPreferenceForm(forms.ModelForm):
    class Meta:
        model = NotificationPreference
        fields = [
            'via_email',
            'via_sms',
            'via_whatsapp',
            'daily_email_limit',  # shown but disabled
            'monthly_email_limit',  # shown but disabled
            'twilio_account_sid',
            'twilio_auth_token',
            'twilio_phone_number',
            'twilio_whatsapp_number',
        ]
        widgets = {
            'twilio_auth_token': forms.PasswordInput(render_value=True),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Disable quota fields in the form
        self.fields['daily_email_limit'].disabled = True
        self.fields['monthly_email_limit'].disabled = True


class SubscriptionForm(forms.ModelForm):
    class Meta:
        model = Subscription
        fields = ['notification_preference']
        widgets = {
            'notification_preference': forms.RadioSelect(),
        }


class AnonymousSubscriptionForm(forms.ModelForm):
    # hcaptcha = hCaptchaField()

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

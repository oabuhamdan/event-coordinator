"""
Forms for user accounts and availability management.
"""
from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from datetime import datetime
import json
from hcaptcha.fields import hCaptchaField

from .models import User
from .services.availability_service import AvailabilityService


# class CaptchaAuthenticationForm(AuthenticationForm):
#     """Custom login form with hCaptcha."""
#     hcaptcha = hCaptchaField()
#
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         # Add Bootstrap classes to form fields
#         self.fields['username'].widget.attrs.update({'class': 'form-control'})
#         self.fields['password'].widget.attrs.update({'class': 'form-control'})


class AvailabilityForm(forms.Form):
    """Form for handling user availability data."""
    availability_data = forms.CharField(widget=forms.HiddenInput(), required=False)

    def clean_availability_data(self):
        """Validate availability data JSON."""
        data = self.cleaned_data.get('availability_data', '[]')
        print(f"DEBUG - Raw availability_data: {repr(data)}")

        if not data or data.strip() == '':
            data = '[]'

        try:
            parsed_data = json.loads(data)
            print(f"DEBUG - Parsed data: {parsed_data}")

            if not isinstance(parsed_data, list):
                raise ValidationError("Availability data must be a list")

            if len(parsed_data) == 0:
                print("DEBUG - No availability data provided - this is allowed for clearing availability")
                return []

            # Validate each item only if data is provided
            for item in parsed_data:
                self._validate_availability_item(item)

            return parsed_data
        except json.JSONDecodeError as e:
            print(f"DEBUG - JSON decode error: {e}")
            raise ValidationError("Invalid availability data format")

    def _validate_availability_item(self, item):
        """Validate individual availability item."""
        if not isinstance(item, dict):
            raise ValidationError("Each availability item must be an object")

        recurrence_type = item.get('recurrence_type', 'weekly')

        # Validate recurrence type requirements
        if recurrence_type == 'weekly' and item.get('day_of_week') is None:
            raise ValidationError("Day of week is required for weekly recurrence")
        elif recurrence_type == 'monthly' and item.get('day_of_month') is None:
            raise ValidationError("Day of month is required for monthly recurrence")
        elif recurrence_type == 'specific_date' and not item.get('specific_date'):
            raise ValidationError("Specific date is required for specific date recurrence")

        # Validate time slots - UPDATED to allow empty time slots
        time_slots = item.get('time_slots', [])
        if not isinstance(time_slots, list):
            raise ValidationError("Time slots must be a list")

        # Allow empty time slots array - this will effectively delete the availability
        if len(time_slots) == 0:
            print(f"DEBUG - Empty time slots for {recurrence_type} - this will clear availability")
            return

        # If time slots are provided, validate them
        for slot in time_slots:
            self._validate_time_slot(slot)

    def _validate_time_slot(self, slot):
        """Validate individual time slot."""
        if not isinstance(slot, dict) or 'start' not in slot or 'end' not in slot:
            raise ValidationError("Each time slot must have 'start' and 'end' times")

        try:
            start_time = datetime.strptime(slot['start'], '%H:%M')
            end_time = datetime.strptime(slot['end'], '%H:%M')
            if start_time >= end_time:
                raise ValidationError("Start time must be before end time")
        except ValueError:
            raise ValidationError("Time slots must be in HH:MM format")

    def save(self, user=None, anonymous_subscription=None, organization=None):
        """Save availability data using the service."""
        availability_data = self.cleaned_data['availability_data']

        print(f"DEBUG - Form.save called with:")
        print(f"  user: {user}")
        print(f"  anonymous_subscription: {anonymous_subscription}")
        print(f"  organization: {organization}")
        print(f"  availability_data: {availability_data}")

        # Always allow saving, even with empty data (for clearing availability)
        return AvailabilityService.update_availability(
            user=user,
            anonymous_subscription=anonymous_subscription,
            organization=organization,
            availability_data=availability_data
        )


class UserRegistrationForm(UserCreationForm):
    """Form for regular user registration."""
    email = forms.EmailField(required=True)
    phone_number = forms.CharField(max_length=20, required=False)
    whatsapp_number = forms.CharField(max_length=20, required=False)
    # hcaptcha = hCaptchaField()

    class Meta:
        model = User
        fields = ('username', 'email', 'phone_number', 'whatsapp_number', 'password1', 'password2')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.user_type = 'user'
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user


class OrganizationRegistrationForm(UserCreationForm):
    """Form for organization registration."""
    email = forms.EmailField(required=True)
    phone_number = forms.CharField(max_length=20, required=False)
    whatsapp_number = forms.CharField(max_length=20, required=False)
    # hcaptcha = hCaptchaField()

    class Meta:
        model = User
        fields = ('username', 'email', 'phone_number', 'whatsapp_number', 'password1', 'password2')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.user_type = 'organization'
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user


class ProfileUpdateForm(forms.ModelForm):
    """Form for updating user profile."""

    class Meta:
        model = User
        fields = ('email', 'phone_number', 'whatsapp_number')
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'whatsapp_number': forms.TextInput(attrs={'class': 'form-control'}),
        }

# events/forms.py
from django import forms
from django.utils import timezone
from .models import Event, EventResponse


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = [
            'title', 'description', 'start_datetime', 'end_datetime',
            'location', 'notify_on_creation', 'notify_hours_before', 'notify_on_deletion'
        ]
        widgets = {
            'start_datetime': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'end_datetime': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'notify_hours_before': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_datetime = cleaned_data.get('start_datetime')
        end_datetime = cleaned_data.get('end_datetime')

        if start_datetime and start_datetime <= timezone.now():
            raise forms.ValidationError(f"Event start time must be in the future. {start_datetime} <= {timezone.now()}")

        if start_datetime and end_datetime and end_datetime <= start_datetime:
            raise forms.ValidationError("Event end time must be after start time.")

        return cleaned_data


class EventResponseForm(forms.ModelForm):
    class Meta:
        model = EventResponse
        fields = ['response']
        widgets = {
            'response': forms.RadioSelect(),
        }
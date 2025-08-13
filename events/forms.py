from django import forms
from django.utils import timezone
from .models import Event, EventResponse


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = [
            'title', 'description', 'date_time', 'duration_hours',
            'location', 'notification_hours_before', 'max_participants'
        ]
        widgets = {
            'date_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'description': forms.Textarea(attrs={'rows': 4}),
        }

    def clean_date_time(self):
        date_time = self.cleaned_data['date_time']
        if date_time <= timezone.now():
            raise forms.ValidationError("Event date and time must be in the future.")
        return date_time



class EventResponseForm(forms.ModelForm):
    class Meta:
        model = EventResponse
        fields = ['response']
        widgets = {
            'response': forms.RadioSelect(),
        }
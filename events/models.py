from datetime import timedelta

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
import json


class UserAvailability(models.Model):
    AVAILABILITY_TYPES = [
        ('sure', 'Sure (Green)'),
        ('maybe', 'Maybe (Yellow)'),
    ]

    DAYS_OF_WEEK = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ]

    RECURRENCE_TYPES = [
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('specific_date', 'Specific Date'),
    ]

    # Can be null for anonymous users
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    anonymous_subscription = models.ForeignKey('organizations.AnonymousSubscription', on_delete=models.CASCADE,
                                               null=True, blank=True)
    organization = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE)

    # Recurrence settings
    recurrence_type = models.CharField(max_length=20, choices=RECURRENCE_TYPES, default='weekly')
    day_of_week = models.IntegerField(choices=DAYS_OF_WEEK, null=True, blank=True)
    day_of_month = models.IntegerField(null=True, blank=True)
    specific_date = models.DateField(null=True, blank=True)

    # Time slots (stored as JSON for multiple time slots per day)
    time_slots = models.JSONField(default=list)

    availability_type = models.CharField(max_length=10, choices=AVAILABILITY_TYPES, default='sure')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        subscriber_name = self.user.username if self.user else (
            self.anonymous_subscription.name if self.anonymous_subscription else 'Unknown')
        return f"{subscriber_name} - {self.organization.name} availability"

    def clean(self):
        if not self.user and not self.anonymous_subscription:
            raise ValidationError("Either user or anonymous_subscription must be set")
        if self.user and self.anonymous_subscription:
            raise ValidationError("Cannot have both user and anonymous_subscription")

        if self.recurrence_type == 'weekly' and self.day_of_week is None:
            raise ValidationError("Day of week is required for weekly recurrence")
        if self.recurrence_type == 'monthly' and self.day_of_month is None:
            raise ValidationError("Day of month is required for monthly recurrence")
        if self.recurrence_type == 'specific_date' and self.specific_date is None:
            raise ValidationError("Specific date is required for specific date recurrence")


class Event(models.Model):
    organization = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    date_time = models.DateTimeField()
    duration_hours = models.DecimalField(max_digits=4, decimal_places=2, default=1.0)
    location = models.CharField(max_length=200, blank=True)
    notification_hours_before = models.IntegerField(default=24)
    max_participants = models.IntegerField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} - {self.date_time}"

    @property
    def end_time(self):
        return self.date_time + timedelta(hours=float(self.duration_hours))

    @property
    def is_upcoming(self):
        return self.date_time > timezone.now()

    def get_response_counts(self):
        responses = EventResponse.objects.filter(event=self)
        return {
            'yes': responses.filter(response='yes').count(),
            'no': responses.filter(response='no').count(),
            'maybe': responses.filter(response='maybe').count(),
        }

    def matches_user_availability(self, user):
        """Check if this event matches user's availability"""
        availabilities = UserAvailability.objects.filter(user=user, organization=self.organization)

        event_weekday = self.date_time.weekday()
        event_time = self.date_time.time()
        event_date = self.date_time.date()
        event_day_of_month = self.date_time.day

        for availability in availabilities:
            # Check weekly recurrence
            if availability.recurrence_type == 'weekly' and availability.day_of_week == event_weekday:
                if self._time_matches_slots(event_time, availability.time_slots):
                    return True

            # Check monthly recurrence
            elif availability.recurrence_type == 'monthly' and availability.day_of_month == event_day_of_month:
                if self._time_matches_slots(event_time, availability.time_slots):
                    return True

            # Check specific date
            elif availability.recurrence_type == 'specific_date' and availability.specific_date == event_date:
                if self._time_matches_slots(event_time, availability.time_slots):
                    return True

        return False

    def _time_matches_slots(self, event_time, time_slots):
        """Check if event time falls within any of the time slots"""
        from datetime import datetime

        for slot in time_slots:
            start_time = datetime.strptime(slot['start'], '%H:%M').time()
            end_time = datetime.strptime(slot['end'], '%H:%M').time()

            if start_time <= event_time <= end_time:
                return True

        return False

    def matches_anonymous_availability(self, anonymous_subscription):
        """Check if this event matches anonymous subscriber's availability"""
        from events.models import UserAvailability

        availabilities = UserAvailability.objects.filter(
            anonymous_subscription=anonymous_subscription,
            organization=self.organization
        )

        event_weekday = self.date_time.weekday()
        event_time = self.date_time.time()
        event_date = self.date_time.date()
        event_day_of_month = self.date_time.day

        for availability in availabilities:
            # Check weekly recurrence
            if availability.recurrence_type == 'weekly' and availability.day_of_week == event_weekday:
                if self._time_matches_slots(event_time, availability.time_slots):
                    return True

            # Check monthly recurrence
            elif availability.recurrence_type == 'monthly' and availability.day_of_month == event_day_of_month:
                if self._time_matches_slots(event_time, availability.time_slots):
                    return True

            # Check specific date
            elif availability.recurrence_type == 'specific_date' and availability.specific_date == event_date:
                if self._time_matches_slots(event_time, availability.time_slots):
                    return True

        return False


class EventResponse(models.Model):
    RESPONSE_CHOICES = [
        ('yes', 'Yes, I will attend'),
        ('no', 'No, I cannot attend'),
        ('maybe', 'Maybe'),
    ]

    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    response = models.CharField(max_length=10, choices=RESPONSE_CHOICES)
    responded_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['event', 'user']

    def __str__(self):
        return f"{self.user.username} - {self.event.title}: {self.response}"


class NotificationLog(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    anonymous_subscription = models.ForeignKey('organizations.AnonymousSubscription', on_delete=models.CASCADE,
                                               null=True, blank=True)
    notification_type = models.CharField(max_length=20)
    sent_at = models.DateTimeField(auto_now_add=True)
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)

    def __str__(self):
        if self.user:
            return f"Notification to {self.user.username} for {self.event.title}"
        else:
            return f"Anonymous notification for {self.event.title}"

    @property
    def recipient_name(self):
        if self.user:
            return self.user.username
        elif self.anonymous_subscription:
            return f"{self.anonymous_subscription.name} (Anonymous)"
        else:
            return "Unknown"

    @property
    def recipient_email(self):
        if self.user:
            return self.user.email
        elif self.anonymous_subscription:
            return self.anonymous_subscription.email
        else:
            return "Unknown"
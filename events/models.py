from datetime import timedelta
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError


class EventManager(models.Manager):
    """Custom manager for Event model with common queries."""

    def upcoming(self):
        """Get upcoming events."""
        return self.filter(date_time__gte=timezone.now())

    def past(self):
        """Get past events."""
        return self.filter(date_time__lt=timezone.now())

    def for_organization(self, organization):
        """Get events for a specific organization."""
        return self.filter(organization=organization)


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

    objects = EventManager()

    class Meta:
        ordering = ['-date_time']

    def __str__(self):
        return f"{self.title} - {self.date_time}"

    @property
    def end_time(self):
        """Calculate event end time."""
        return self.date_time + timedelta(hours=float(self.duration_hours))

    @property
    def is_upcoming(self):
        """Check if event is upcoming."""
        return self.date_time > timezone.now()


class EventResponse(models.Model):
    RESPONSE_CHOICES = [
        ('yes', 'Yes, I will attend'),
        ('no', 'No, I cannot attend'),
        ('maybe', 'Maybe'),
    ]

    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    anonymous_subscription = models.ForeignKey('organizations.AnonymousSubscription',
                                               on_delete=models.CASCADE, null=True, blank=True)
    response = models.CharField(max_length=10, choices=RESPONSE_CHOICES)
    responded_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [
            ['event', 'user'],
            ['event', 'anonymous_subscription']
        ]

    def __str__(self):
        responder = self.user.username if self.user else (
            self.anonymous_subscription.name if self.anonymous_subscription else 'Unknown'
        )
        return f"{responder} - {self.event.title}: {self.response}"

    def clean(self):
        if not self.user and not self.anonymous_subscription:
            raise ValidationError("Either user or anonymous_subscription must be set")
        if self.user and self.anonymous_subscription:
            raise ValidationError("Cannot have both user and anonymous_subscription")

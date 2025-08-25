# events/models.py
from datetime import timedelta
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError


class EventManager(models.Manager):
    """Custom manager for Event model with common queries."""

    def upcoming(self):
        """Get upcoming events."""
        return self.filter(start_datetime__gte=timezone.now())

    def past(self):
        """Get past events."""
        return self.filter(end_datetime__lt=timezone.now())

    def for_organization(self, organization):
        """Get events for a specific organization."""
        return self.filter(organization=organization)


class Event(models.Model):
    organization = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=250, blank=True)  # Make it blank for now
    description = models.TextField(blank=True)

    # Updated datetime fields
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()

    location = models.CharField(max_length=200, blank=True)

    # Notification settings
    notify_on_creation = models.BooleanField(default=True)
    notify_hours_before = models.IntegerField(default=24)
    notify_on_deletion = models.BooleanField(default=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = EventManager()

    class Meta:
        ordering = ['-start_datetime']
        # Remove unique_together for now since we need to populate slugs first

    def __str__(self):
        return f"{self.title} - {self.start_datetime}"

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            import uuid
            base_slug = slugify(self.title)
            if not base_slug:  # If title has no valid characters for slug
                base_slug = f"event-{uuid.uuid4().hex[:8]}"

            self.slug = base_slug

            # Ensure uniqueness within organization
            counter = 1
            original_slug = self.slug
            while Event.objects.filter(organization=self.organization, slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1

        super().save(*args, **kwargs)

    @property
    def duration_hours(self):
        """Calculate duration in hours."""
        if self.end_datetime and self.start_datetime:
            delta = self.end_datetime - self.start_datetime
            return delta.total_seconds() / 3600
        return 0

    @property
    def is_upcoming(self):
        """Check if event is upcoming."""
        return self.start_datetime > timezone.now()

    def clean(self):
        if self.end_datetime and self.start_datetime and self.end_datetime <= self.start_datetime:
            raise ValidationError("End datetime must be after start datetime")


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

    def clean(self):
        if not self.user and not self.anonymous_subscription:
            raise ValidationError("Either user or anonymous_subscription must be set")
        if self.user and self.anonymous_subscription:
            raise ValidationError("Cannot have both user and anonymous_subscription")

    def __str__(self):
        responder = self.user.username if self.user else (
            self.anonymous_subscription.name if self.anonymous_subscription else 'Unknown'
        )
        return f"{responder} - {self.event.title}: {self.response}"
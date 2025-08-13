from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.exceptions import ValidationError


class User(AbstractUser):
    """Extended user model with user type and contact information."""
    USER_TYPE_CHOICES = [
        ('user', 'Regular User'),
        ('organization', 'Organization'),
    ]

    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default='user')
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    whatsapp_number = models.CharField(max_length=20, blank=True, null=True)
    email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.username} ({self.get_user_type_display()})"

    @property
    def is_organization(self):
        return self.user_type == 'organization'

    @property
    def is_regular_user(self):
        return self.user_type == 'user'


class UserSession(models.Model):
    """Track user sessions and device information."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    session_key = models.CharField(max_length=40, blank=True, null=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-last_activity']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['session_key', 'ip_address']),
        ]

    def __str__(self):
        user_info = self.user.username if self.user else f"Anonymous-{self.ip_address}"
        return f"{user_info} - {self.ip_address}"


class UserAvailability(models.Model):
    """User availability preferences for organizations."""
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

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    anonymous_subscription = models.ForeignKey(
        'organizations.AnonymousSubscription',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    organization = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE)

    recurrence_type = models.CharField(max_length=20, choices=RECURRENCE_TYPES, default='weekly')
    day_of_week = models.IntegerField(choices=DAYS_OF_WEEK, null=True, blank=True)
    day_of_month = models.IntegerField(null=True, blank=True)
    specific_date = models.DateField(null=True, blank=True)

    time_slots = models.JSONField(default=list)
    availability_type = models.CharField(max_length=10, choices=AVAILABILITY_TYPES, default='sure')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'organization']),
            models.Index(fields=['anonymous_subscription', 'organization']),
            models.Index(fields=['organization', 'recurrence_type']),
            models.Index(fields=['day_of_week', 'availability_type']),
        ]

    def __str__(self):
        subscriber_name = self.user.username if self.user else (
            self.anonymous_subscription.name if self.anonymous_subscription else 'Unknown')
        return f"{subscriber_name} - {self.organization.name} availability"

    def clean(self):
        """Validate model constraints."""
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

        if not self.time_slots or not isinstance(self.time_slots, list):
            raise ValidationError("Time slots must be a non-empty list")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
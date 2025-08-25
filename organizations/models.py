from django.conf import settings
from django.db import models


class Organization(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    website = models.URLField(blank=True)
    logo = models.ImageField(upload_to='organization_logos/', blank=True, null=True)
    contact_email = models.EmailField(default='<EMAIL>')
    contact_phone = models.CharField(max_length=20, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def get_enhanced_availability_analytics(self, start_date=None, end_date=None):
        """Get enhanced analytics with simplified overlap detection"""
        from organizations.analytics import get_availability_analytics
        return get_availability_analytics(self, start_date, end_date)

    def get_datetime_slot_subscriber_details(self, datetime_slot, start_date, end_date):
        """Get detailed subscriber info for a specific datetime slot"""
        from organizations.analytics import get_datetime_slot_subscriber_details
        return get_datetime_slot_subscriber_details(self, datetime_slot, start_date, end_date)

    # Add this method to Organization model in organizations/models.py

    def get_top_availability_slots(self, limit=3, days_ahead=30):
        """Get top availability slots for event suggestions."""
        from datetime import timedelta
        from django.utils import timezone

        start_date = timezone.now().date()
        end_date = start_date + timedelta(days=days_ahead)

        analytics = self.get_enhanced_availability_analytics(start_date, end_date)

        if not analytics.get('datetime_slot_scores'):
            return []

        # Get top slots sorted by subscriber count
        top_slots = sorted(
            analytics['datetime_slot_scores'].items(),
            key=lambda x: x[1]['total_count'],
            reverse=True
        )[:limit]

        suggestions = []
        for datetime_slot, data in top_slots:
            date_part, time_part = datetime_slot.split(' ')
            start_time, end_time = time_part.split('-')

            suggestions.append({
                'date': date_part,
                'start_time': start_time,
                'end_time': end_time,
                'subscriber_count': data['total_count'],
                'display': data['display'],
                'formatted_date': data['formatted_date'],
                'day_name': data['day_name']
            })

        return suggestions


class NotificationPreference(models.Model):
    organization = models.OneToOneField(
        Organization,
        on_delete=models.CASCADE,
        related_name='notification_preferences'
    )

    # === Channel Preferences ===
    via_email = models.BooleanField(default=True)
    via_sms = models.BooleanField(default=False)
    via_whatsapp = models.BooleanField(default=False)

    # === Email Usage Limits ===
    daily_email_limit = models.IntegerField(default=100)
    monthly_email_limit = models.IntegerField(default=1000)
    used_today = models.IntegerField(default=0)
    used_this_month = models.IntegerField(default=0)

    last_reset_day = models.DateField(auto_now_add=True)
    last_reset_month = models.DateField(auto_now_add=True)

    # === Twilio Configuration ===
    twilio_account_sid = models.CharField(max_length=200, blank=True)
    twilio_auth_token = models.CharField(max_length=200, blank=True)  # 🔐 consider encrypting
    twilio_phone_number = models.CharField(max_length=20, blank=True)
    twilio_whatsapp_number = models.CharField(max_length=20, blank=True)

    def has_exceeded_daily_limit(self):
        return self.used_today >= self.daily_email_limit

    def has_exceeded_monthly_limit(self):
        return self.used_this_month >= self.monthly_email_limit

    def __str__(self):
        return f"Notification settings for {self.organization.name}"


class Subscription(models.Model):
    NOTIFICATION_PREFERENCES = [
        ('all', 'All Events'),
        ('matching', 'Only Matching Schedule'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    notification_preference = models.CharField(max_length=20, choices=NOTIFICATION_PREFERENCES, default='all')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'organization']

    def __str__(self):
        return f"{self.user.username} - {self.organization.name}"


class AnonymousSubscription(models.Model):
    NOTIFICATION_PREFERENCES = [
        ('all', 'All Events'),
        ('matching', 'Only Matching Schedule'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone_number = models.CharField(max_length=20, blank=True)
    whatsapp_number = models.CharField(max_length=20, blank=True)
    notification_preference = models.CharField(max_length=20, choices=NOTIFICATION_PREFERENCES, default='all')

    # Verification fields
    is_verified = models.BooleanField(default=False)
    verification_token = models.CharField(max_length=100, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['email', 'organization']

    def __str__(self):
        return f"{self.name} ({self.email}) - {self.organization.name}"

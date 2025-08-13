from django.conf import settings
from django.db import models


class Organization(models.Model):
    NOTIFICATION_TYPES = [
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('whatsapp', 'WhatsApp'),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    website = models.URLField(blank=True)
    logo = models.ImageField(upload_to='organization_logos/', blank=True, null=True)

    # API Configurations
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='email')

    # Email API settings
    smtp_host = models.CharField(max_length=200, blank=True)
    smtp_port = models.IntegerField(blank=True, null=True)
    smtp_username = models.CharField(max_length=200, blank=True)
    smtp_password = models.CharField(max_length=200, blank=True)

    # SMS/WhatsApp API settings (Twilio)
    twilio_account_sid = models.CharField(max_length=200, blank=True)
    twilio_auth_token = models.CharField(max_length=200, blank=True)
    twilio_phone_number = models.CharField(max_length=20, blank=True)
    twilio_whatsapp_number = models.CharField(max_length=20, blank=True)

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
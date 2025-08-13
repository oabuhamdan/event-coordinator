from django.db import models
from django.conf import settings


class NotificationLog(models.Model):
    """
    Logs all notifications sent through the system.
    Tracks both registered users and anonymous subscribers.
    """
    event = models.ForeignKey('events.Event', on_delete=models.CASCADE)
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
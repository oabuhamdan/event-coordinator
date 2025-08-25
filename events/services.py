# events/services.py
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from django.db.models import QuerySet, Count
from django.utils import timezone
from django.template.loader import render_to_string
from django.conf import settings

from .models import Event, EventResponse
from organizations.models import Organization, Subscription, AnonymousSubscription


class EventService:
    """Handles event creation, updates, and deletion."""

    @staticmethod
    def get_response_counts(event):
        """Get response statistics for an event."""
        responses = EventResponse.objects.filter(event=event)
        return {
            'yes': responses.filter(response='yes').count(),
            'no': responses.filter(response='no').count(),
            'maybe': responses.filter(response='maybe').count(),
            'total': responses.count()
        }


class NotificationService:
    """Handles event notifications."""

    @staticmethod
    def send_event_creation_notifications(event):
        """Send notifications for new event creation."""
        from notifications.tasks import send_event_notifications
        
        try:
            send_event_notifications.delay(event.pk, notification_type='creation')
        except Exception as e:
            # Fallback for development without Celery
            send_event_notifications(event.pk, notification_type='creation')

    @staticmethod
    def send_event_deletion_notifications(event):
        """Send notifications for event deletion."""
        from notifications.tasks import send_event_notifications
        
        try:
            send_event_notifications.delay(event.pk, notification_type='deletion')
        except Exception as e:
            # Fallback for development without Celery
            send_event_notifications(event.pk, notification_type='deletion')

    @staticmethod
    def render_notification_template(template_name, context):
        """Render notification template with context."""
        try:
            content = render_to_string(template_name, context)
            return content.strip()
        except Exception as e:
            return f"Error rendering template {template_name}: {str(e)}"
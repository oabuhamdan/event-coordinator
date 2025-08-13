"""
Event-related business logic services.
Following Single Responsibility Principle - each service handles one specific domain.
"""
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from django.db.models import QuerySet
from django.utils import timezone
from django.contrib.auth import get_user_model

from .models import Event, EventResponse
from accounts.models import UserAvailability
from accounts.utils import is_organization_user, is_regular_user
from organizations.models import Organization, Subscription, AnonymousSubscription

User = get_user_model()


class EventService:
    """Handles event creation, updates, and deletion."""

    @staticmethod
    def create_event(organization, event_data):
        """Create a new event for an organization."""
        event = Event.objects.create(
            organization=organization,
            **event_data
        )

        # Schedule notifications (if notifications app is available)
        try:
            from notifications.tasks import send_event_notifications
            send_event_notifications.delay(event.pk)
        except ImportError:
            pass

        return event

    @staticmethod
    def update_event(event, event_data):
        """Update an existing event."""
        for field, value in event_data.items():
            setattr(event, field, value)
        event.save()
        return event

    @staticmethod
    def delete_event(event):
        """Delete an event."""
        event.delete()


class EventQueryService:
    """Handles event queries and filtering."""

    @staticmethod
    def get_upcoming_events():
        """Get all upcoming events."""
        return Event.objects.filter(date_time__gte=timezone.now()).order_by('date_time')

    @staticmethod
    def get_past_events():
        """Get all past events."""
        return Event.objects.filter(date_time__lt=timezone.now()).order_by('-date_time')

    @staticmethod
    def get_organization_events(organization):
        """Get all events for an organization."""
        return Event.objects.filter(organization=organization)

    @staticmethod
    def get_event_response_stats(event):
        """Get response statistics for an event."""
        responses = EventResponse.objects.filter(event=event)

        stats = {
            'yes': responses.filter(response='yes').count(),
            'no': responses.filter(response='no').count(),
            'maybe': responses.filter(response='maybe').count(),
            'total_responses': responses.count()
        }

        return stats


class AvailabilityManagementService:
    """Handles availability management operations."""

    @staticmethod
    def get_user_availability(user, organization):
        """Get availability for a user in an organization."""
        return UserAvailability.objects.filter(user=user, organization=organization)

    @staticmethod
    def get_anonymous_availability(anonymous_subscription, organization):
        """Get availability for an anonymous subscription."""
        return UserAvailability.objects.filter(
            anonymous_subscription=anonymous_subscription,
            organization=organization
        )

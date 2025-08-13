"""
Availability service for handling user availability operations.
"""
from django.db import transaction
from django.core.exceptions import ValidationError
from datetime import datetime
from typing import List, Dict, Optional, Union

from ..models import UserAvailability
from organizations.models import Organization, AnonymousSubscription


class AvailabilityService:
    """Service for managing user availability operations."""

    @staticmethod
    def get_user_availability(user=None, anonymous_subscription=None, organization=None):
        """Get availability records for user or anonymous subscription."""
        if user:
            return UserAvailability.objects.filter(
                user=user,
                organization=organization
            ).order_by('recurrence_type', 'day_of_week', 'day_of_month')
        elif anonymous_subscription:
            return UserAvailability.objects.filter(
                anonymous_subscription=anonymous_subscription,
                organization=organization
            ).order_by('recurrence_type', 'day_of_week', 'day_of_month')
        return UserAvailability.objects.none()

    @staticmethod
    @transaction.atomic
    def update_availability(
            user=None,
            anonymous_subscription=None,
            organization=None,
            availability_data: List[Dict] = None
    ):
        """Update user availability preferences."""
        if not organization:
            raise ValidationError("Organization is required")

        if not user and not anonymous_subscription:
            raise ValidationError("Either user or anonymous_subscription is required")

        if user and anonymous_subscription:
            raise ValidationError("Cannot specify both user and anonymous_subscription")

        # Clear existing availability
        if user:
            UserAvailability.objects.filter(user=user, organization=organization).delete()
        else:
            UserAvailability.objects.filter(
                anonymous_subscription=anonymous_subscription,
                organization=organization
            ).delete()

        # If no availability data provided, just return empty list (clearing availability)
        if not availability_data:
            print("DEBUG - No availability data provided, cleared existing availability")
            return []

        # Create new availability records
        created_records = []
        for item in availability_data or []:
            try:
                specific_date = None
                if item.get('recurrence_type') == 'specific_date' and item.get('specific_date'):
                    specific_date = AvailabilityService._parse_date(item.get('specific_date'))

                availability = UserAvailability(
                    user=user,
                    anonymous_subscription=anonymous_subscription,
                    organization=organization,
                    recurrence_type=item.get('recurrence_type', 'weekly'),
                    day_of_week=item.get('day_of_week'),
                    day_of_month=item.get('day_of_month'),
                    specific_date=specific_date,
                    time_slots=item.get('time_slots', []),
                    availability_type=item.get('availability_type', 'sure')
                )
                availability.full_clean()
                availability.save()
                created_records.append(availability)
            except ValidationError as e:
                print(f"Validation error for availability record: {e}")
                continue

        return created_records

    @staticmethod
    def _parse_date(date_str):
        """Parse date string safely."""
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            try:
                return datetime.fromisoformat(date_str).date()
            except (ValueError, TypeError):
                return None

    @staticmethod
    def serialize_availability(availability_queryset):
        """Serialize availability queryset to JSON-friendly format."""
        data = []
        for avail in availability_queryset:
            data.append({
                'id': avail.id,
                'recurrence_type': avail.recurrence_type,
                'day_of_week': avail.day_of_week,
                'day_of_month': avail.day_of_month,
                'specific_date': avail.specific_date.isoformat() if avail.specific_date else None,
                'time_slots': avail.time_slots,
                'availability_type': avail.availability_type,
            })
        return data
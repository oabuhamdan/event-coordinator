# accounts/services/availability_service.py
"""
Availability service for handling user availability operations.
"""
from datetime import datetime
from typing import List, Dict

from django.core.exceptions import ValidationError
from django.db import transaction

from ..models import UserAvailability


class AvailabilityService:
    """Service for managing user availability operations."""

    @staticmethod
    def get_user_availability(user=None, anonymous_subscription=None, organization=None):
        """Get availability records for user or anonymous subscription."""
        if user:
            return UserAvailability.objects.filter(
                user=user,
                organization=organization
            ).order_by('recurrence_type', 'day_of_week')
        elif anonymous_subscription:
            return UserAvailability.objects.filter(
                anonymous_subscription=anonymous_subscription,
                organization=organization
            ).order_by('recurrence_type', 'day_of_week')
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
                    day_of_month=None,  # Always None since monthly is removed
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
                'specific_date': avail.specific_date.isoformat() if avail.specific_date else None,
                'time_slots': avail.time_slots,
                'availability_type': avail.availability_type,
            })
        return data

    @staticmethod
    def user_matches_event(user, event):
        """Check if a user's availability matches an event's date and time."""
        try:
            # Get user's availability for this organization
            availabilities = UserAvailability.objects.filter(
                user=user,
                organization=event.organization
            )
            
            return AvailabilityService._check_event_match(availabilities, event)
        except Exception as e:
            print(f"Error checking user availability match: {e}")
            return False

    @staticmethod
    def anonymous_matches_event(anonymous_subscription, event):
        """Check if an anonymous subscription's availability matches an event's date and time."""
        try:
            # Get anonymous subscription's availability for this organization
            availabilities = UserAvailability.objects.filter(
                anonymous_subscription=anonymous_subscription,
                organization=event.organization
            )
            
            return AvailabilityService._check_event_match(availabilities, event)
        except Exception as e:
            print(f"Error checking anonymous availability match: {e}")
            return False

    @staticmethod
    def _check_event_match(availabilities, event):
        """Check if any availability record matches the event time."""
        if not availabilities.exists():
            return False

        event_date = event.start_datetime.date()
        event_start_time = event.start_datetime.time()
        event_end_time = event.end_datetime.time() if event.end_datetime else event_start_time

        for availability in availabilities:
            # Check if this availability applies to the event date
            if availability.recurrence_type == 'weekly':
                # Check if event day matches availability day of week
                if event_date.weekday() != availability.day_of_week:
                    continue
            elif availability.recurrence_type == 'specific_date':
                # Check if event date matches specific date
                if event_date != availability.specific_date:
                    continue
            else:
                # Skip any other recurrence types (shouldn't exist)
                continue

            # Check if event time overlaps with any of the availability time slots
            for time_slot in availability.time_slots:
                try:
                    slot_start = datetime.strptime(time_slot['start'], '%H:%M').time()
                    slot_end = datetime.strptime(time_slot['end'], '%H:%M').time()
                    
                    # Check if event time overlaps with this time slot
                    if AvailabilityService._times_overlap(
                        event_start_time, event_end_time,
                        slot_start, slot_end
                    ):
                        return True
                except (KeyError, ValueError, TypeError):
                    # Skip invalid time slots
                    continue

        return False

    @staticmethod
    def _times_overlap(start1, end1, start2, end2):
        """Check if two time ranges overlap."""
        # Convert times to minutes for easier comparison
        def time_to_minutes(t):
            return t.hour * 60 + t.minute

        start1_min = time_to_minutes(start1)
        end1_min = time_to_minutes(end1)
        start2_min = time_to_minutes(start2)
        end2_min = time_to_minutes(end2)

        # Check for overlap: ranges overlap if start1 < end2 and start2 < end1
        return start1_min < end2_min and start2_min < end1_min

    @staticmethod
    def get_matching_subscribers(organization, event):
        """Get all subscribers whose availability matches the event."""
        matching_users = []
        matching_anonymous = []

        # Check regular subscribers
        from organizations.models import Subscription
        subscriptions = Subscription.objects.filter(organization=organization).select_related('user')
        
        for subscription in subscriptions:
            if subscription.notification_preference == 'matching':
                if AvailabilityService.user_matches_event(subscription.user, event):
                    matching_users.append(subscription.user)
            elif subscription.notification_preference == 'all':
                matching_users.append(subscription.user)

        # Check anonymous subscribers
        from organizations.models import AnonymousSubscription
        anon_subscriptions = AnonymousSubscription.objects.filter(organization=organization)
        
        for anon_sub in anon_subscriptions:
            if anon_sub.notification_preference == 'matching':
                if AvailabilityService.anonymous_matches_event(anon_sub, event):
                    matching_anonymous.append(anon_sub)
            elif anon_sub.notification_preference == 'all':
                matching_anonymous.append(anon_sub)

        return {
            'users': matching_users,
            'anonymous': matching_anonymous,
            'total_count': len(matching_users) + len(matching_anonymous)
        }
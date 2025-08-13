"""
Organization-related business logic services.
Following Single Responsibility Principle for clean separation of concerns.
"""
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from django.db.models import QuerySet
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction

from .models import Organization, Subscription, AnonymousSubscription
from events.models import Event

User = get_user_model()


def get_client_ip(request):
    """Get the client's IP address from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


class OrganizationService:
    """Handles organization profile operations."""
    
    @staticmethod
    def create_organization(user: User, organization_data: Dict) -> Organization:
        """Create a new organization profile."""
        organization = Organization.objects.create(user=user, **organization_data)
        return organization
    
    @staticmethod
    def update_organization(organization: Organization, organization_data: Dict) -> Organization:
        """Update an existing organization."""
        for field, value in organization_data.items():
            setattr(organization, field, value)
        organization.save()
        return organization
    
    @staticmethod
    def get_organization_for_user(user: User) -> Optional[Organization]:
        """Get organization for a user, returns None if not found."""
        try:
            return Organization.objects.get(user=user)
        except Organization.DoesNotExist:
            return None

    @staticmethod
    @transaction.atomic
    def delete_organization(organization: Organization):
        """Delete an organization."""
        organization.delete()


class SubscriptionService:
    """Handles subscription operations."""
    
    @staticmethod
    def subscribe_user(user: User, organization: Organization) -> Tuple[Subscription, bool]:
        """Subscribe a user to an organization. Returns (subscription, created)."""
        return Subscription.objects.get_or_create(user=user, organization=organization)
    
    @staticmethod
    def unsubscribe_user(user: User, organization: Organization) -> bool:
        """Unsubscribe a user from an organization. Returns True if subscription existed."""
        try:
            subscription = Subscription.objects.get(user=user, organization=organization)
            subscription.delete()
            return True
        except Subscription.DoesNotExist:
            return False
    
    @staticmethod
    def is_user_subscribed(user: User, organization: Organization) -> bool:
        """Check if user is subscribed to organization."""
        return Subscription.objects.filter(user=user, organization=organization).exists()
    
    @staticmethod
    def get_user_subscriptions(user: User) -> QuerySet:
        """Get all subscriptions for a user."""
        return Subscription.objects.filter(user=user).select_related('organization')

    @staticmethod
    @transaction.atomic
    def create_subscription(user, organization, subscription_data):
        """Create a subscription for a user."""
        subscription, created = Subscription.objects.get_or_create(
            user=user,
            organization=organization,
            defaults=subscription_data
        )
        return subscription

    @staticmethod
    @transaction.atomic
    def create_anonymous_subscription(organization, subscription_data):
        """Create an anonymous subscription."""
        subscription = AnonymousSubscription.objects.create(
            organization=organization,
            **subscription_data
        )
        return subscription

    @staticmethod
    def delete_subscription(user, organization):
        """Delete a user's subscription to an organization."""
        try:
            subscription = Subscription.objects.get(user=user, organization=organization)
            subscription.delete()

            # Also delete any availability data for this user/organization
            from accounts.models import UserAvailability
            UserAvailability.objects.filter(user=user, organization=organization).delete()

            return True
        except Subscription.DoesNotExist:
            return False

    @staticmethod
    def get_organization_subscribers(organization: Organization) -> Dict:
        """Get all subscribers for an organization."""
        regular_subscribers = Subscription.objects.filter(organization=organization).select_related('user')
        anonymous_subscribers = AnonymousSubscription.objects.filter(organization=organization)

        return {
            'regular_subscribers': regular_subscribers,
            'anonymous_subscribers': anonymous_subscribers,
            'total_count': regular_subscribers.count() + anonymous_subscribers.count()
        }


class OrganizationQueryService:
    """Handles organization queries and listings."""
    
    @staticmethod
    def get_all_organizations() -> QuerySet:
        """Get all organizations ordered by name."""
        return Organization.objects.all().order_by('name')
    
    @staticmethod
    def get_organization_with_events(organization: Organization, limit: int = 5) -> Dict:
        """Get organization with upcoming events."""
        upcoming_events = Event.objects.filter(
            organization=organization,
            date_time__gte=timezone.now()
        ).order_by('date_time')[:limit]
        
        return {
            'organization': organization,
            'upcoming_events': upcoming_events,
        }
    
    @staticmethod
    def search_organizations(query: str) -> QuerySet:
        """Search organizations by name or description."""
        return Organization.objects.filter(
            name__icontains=query
        ).order_by('name')


class OrganizationAnalyticsService:
    """Handles organization analytics and dashboard data."""

    @staticmethod
    def get_dashboard_stats(organization: Organization) -> Dict:
        """Get dashboard statistics for an organization."""
        regular_subscribers = Subscription.objects.filter(organization=organization).count()
        anonymous_subscribers = AnonymousSubscription.objects.filter(organization=organization).count()
        total_subscribers = regular_subscribers + anonymous_subscribers
        total_events = Event.objects.filter(organization=organization).count()
        upcoming_events = Event.objects.filter(
            organization=organization,
            date_time__gte=timezone.now()
        ).count()

        recent_events = Event.objects.filter(organization=organization).order_by('-created_at')[:5]

        return {
            'total_subscribers': total_subscribers,
            'regular_subscribers': regular_subscribers,
            'anonymous_subscribers': anonymous_subscribers,
            'total_events': total_events,
            'upcoming_events': upcoming_events,
            'recent_events': recent_events,
        }

    @staticmethod
    def get_availability_analytics(organization: Organization, start_date: datetime.date,
                                 end_date: datetime.date) -> Dict:
        """Get availability analytics for date range."""
        return organization.get_enhanced_availability_analytics(start_date, end_date)

    @staticmethod
    def get_subscriber_details(organization: Organization) -> Dict:
        """Get detailed subscriber information."""
        regular_subscribers = Subscription.objects.filter(organization=organization).select_related('user')
        anonymous_subscribers = AnonymousSubscription.objects.filter(organization=organization)

        return {
            'regular_subscribers': regular_subscribers,
            'anonymous_subscribers': anonymous_subscribers,
            'total_regular': regular_subscribers.count(),
            'total_anonymous': anonymous_subscribers.count(),
        }


class DateRangeService:
    """Handles date range parsing and validation."""
    
    @staticmethod
    def parse_date_range(start_date_str: Optional[str], end_date_str: Optional[str], 
                        default_days: int = 30) -> Tuple[datetime.date, datetime.date]:
        """Parse date range from strings with defaults."""
        today = timezone.now().date()
        start_date = today
        end_date = today + timedelta(days=default_days)
        
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        
        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        
        return start_date, end_date
    
    @staticmethod
    def validate_date_range(start_date: datetime.date, end_date: datetime.date) -> bool:
        """Validate that date range is logical."""
        return start_date <= end_date

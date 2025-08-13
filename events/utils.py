"""
Utility functions for user type checking and permissions.
"""
from django.contrib.auth import get_user_model
from accounts.utils import is_organization_user, is_regular_user

User = get_user_model()


def get_user_organization(user):
    """Get organization for a user, returns None if not found."""
    if not is_organization_user(user):
        return None
    return getattr(user, 'organization', None)


def can_user_manage_event(user, event):
    """Check if user can manage (edit/delete) an event."""
    if not is_organization_user(user):
        return False

    try:
        return user.organization == event.organization
    except:
        return False

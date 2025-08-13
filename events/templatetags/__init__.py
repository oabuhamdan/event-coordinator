"""
Custom template tags for clean UI logic separation.
"""
from django import template
from events.utils import is_organization_user, is_regular_user

register = template.Library()


@register.filter
def is_organization(user):
    """Check if user is an organization."""
    return is_organization_user(user)


@register.filter
def is_regular_user_filter(user):
    """Check if user is a regular user."""
    return is_regular_user(user)


@register.inclusion_tag('components/user_badge.html')
def user_badge(user):
    """Render user type badge."""
    return {
        'user': user,
        'is_organization': is_organization_user(user),
        'is_regular': is_regular_user(user)
    }


@register.inclusion_tag('components/event_card.html')
def event_card(event, user=None, show_actions=True):
    """Render event card component."""
    return {
        'event': event,
        'user': user,
        'show_actions': show_actions,
        'can_manage': user and is_organization_user(user) and hasattr(user, 'organization') and event.organization.user == user
    }


@register.inclusion_tag('components/loading_spinner.html')
def loading_spinner(size='md', text='Loading...'):
    """Render loading spinner."""
    return {
        'size': size,
        'text': text
    }


@register.simple_tag
def event_status_class(event):
    """Get CSS class for event status."""
    if event.is_upcoming:
        return 'text-success'
    return 'text-muted'


@register.simple_tag
def event_status_icon(event):
    """Get icon for event status."""
    if event.is_upcoming:
        return 'fas fa-calendar-check'
    return 'fas fa-calendar-times'

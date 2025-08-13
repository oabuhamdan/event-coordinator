from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from functools import wraps
from .models import UserSession


def get_client_ip(request):
    """Get the client's IP address from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_user_agent(request):
    """Get the user agent from request."""
    return request.META.get('HTTP_USER_AGENT', '')


def track_user_session(request, user=None):
    """Track user session and device information."""
    ip_address = get_client_ip(request)
    user_agent = get_user_agent(request)
    session_key = request.session.session_key
    
    # Create or update session tracking
    session_data = {
        'ip_address': ip_address,
        'user_agent': user_agent,
        'session_key': session_key,
    }
    
    if user and user.is_authenticated:
        session_data['user'] = user
        UserSession.objects.update_or_create(
            user=user,
            session_key=session_key,
            defaults=session_data
        )
    else:
        # For anonymous users, track by IP and session
        UserSession.objects.update_or_create(
            session_key=session_key,
            ip_address=ip_address,
            defaults=session_data
        )


def is_organization_user(user):
    """Check if user is an organization user."""
    return user.is_authenticated and user.is_organization


def is_regular_user(user):
    """Check if user is a regular user."""
    return user.is_authenticated and user.is_regular_user


def organization_required(view_func):
    """Decorator to require organization user."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not is_organization_user(request.user):
            raise PermissionDenied("Only organizations can access this page.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def regular_user_required(view_func):
    """Decorator to require regular user."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not is_regular_user(request.user):
            raise PermissionDenied("Only regular users can access this page.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def organization_owner_required(view_func):
    """Decorator to require organization owner."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not is_organization_user(request.user):
            raise PermissionDenied("Only organizations can access this page.")
        
        # Check if user owns the organization being accessed
        organization_id = kwargs.get('pk') or kwargs.get('organization_id')
        if organization_id:
            try:
                organization = request.user.organization
                if organization.id != int(organization_id):
                    raise PermissionDenied("You can only access your own organization.")
            except:
                raise PermissionDenied("Organization not found.")
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view

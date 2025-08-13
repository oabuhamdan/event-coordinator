"""
Session service for tracking user sessions.
"""
from ..models import UserSession
from ..utils import get_client_ip, get_user_agent


class SessionService:
    """Service for managing user sessions and tracking."""

    @staticmethod
    def track_session(request, user=None):
        """Track user session and device information."""
        ip_address = get_client_ip(request)
        user_agent = get_user_agent(request)
        session_key = request.session.session_key

        if not session_key:
            request.session.create()
            session_key = request.session.session_key

        session_data = {
            'ip_address': ip_address,
            'user_agent': user_agent,
        }

        if user and user.is_authenticated:
            session_data['user'] = user
            session, created = UserSession.objects.update_or_create(
                user=user,
                session_key=session_key,
                defaults=session_data
            )
        else:
            session, created = UserSession.objects.update_or_create(
                session_key=session_key,
                ip_address=ip_address,
                defaults=session_data
            )

        return session

    @staticmethod
    def get_user_sessions(user):
        """Get all active sessions for a user."""
        return UserSession.objects.filter(user=user, is_active=True)

    @staticmethod
    def deactivate_session(session_key):
        """Deactivate a session."""
        UserSession.objects.filter(session_key=session_key).update(is_active=False)
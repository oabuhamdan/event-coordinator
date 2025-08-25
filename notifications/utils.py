# notifications/utils.py - Cleaned up version
"""
Utility functions for notifications.
This module contains helper functions for sending notifications.
"""
import logging
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


def log_notification(event, user=None, anonymous_subscription=None, notification_type='email', success=True, error_message=''):
    """Log a notification in the database"""
    from notifications.models import NotificationLog

    # Create notification log
    log = NotificationLog.objects.create(
        event=event,
        user=user,
        anonymous_subscription=anonymous_subscription,
        notification_type=notification_type,
        success=success,
        error_message=error_message
    )

    # Log to console/file
    recipient = user.username if user else (
        f"{anonymous_subscription.name} ({anonymous_subscription.email})" if anonymous_subscription else "Unknown"
    )

    if success:
        logger.info(f"{notification_type.upper()} sent successfully to {recipient} for event {event.id}")
    else:
        logger.error(f"Failed to send {notification_type.upper()} to {recipient} for event {event.id}: {error_message}")

    return log


def render_email_template(template_name, context, fallback_text=None):
    """Render an email template with fallback to plain text"""
    try:
        html_message = render_to_string(template_name, context)
        text_message = strip_tags(html_message)
        return {
            'html_message': html_message,
            'text_message': text_message
        }
    except Exception as e:
        logger.warning(f"Could not render template {template_name}, using fallback: {e}")
        return {
            'html_message': None,
            'text_message': fallback_text
        }


def send_email(recipient_email, subject, text_message, html_message=None):
    """Send an email using Django's send_mail"""
    return send_mail(
        subject=subject,
        message=text_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[recipient_email],
        html_message=html_message,
        fail_silently=False,
    )
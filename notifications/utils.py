"""
Utility functions for notifications.
This module contains helper functions for sending notifications.
"""
import logging
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

# Import Twilio only if available
try:
    from twilio.rest import Client
    from twilio.base.exceptions import TwilioException
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    TwilioException = Exception

logger = logging.getLogger(__name__)


def get_twilio_credentials(organization):
    """Get Twilio credentials from organization or settings"""
    account_sid = getattr(organization, 'twilio_account_sid', None) or getattr(settings, 'TWILIO_ACCOUNT_SID', None)
    auth_token = getattr(organization, 'twilio_auth_token', None) or getattr(settings, 'TWILIO_AUTH_TOKEN', None)
    phone_number = getattr(organization, 'twilio_phone_number', None) or getattr(settings, 'TWILIO_PHONE_NUMBER', None)
    whatsapp_number = getattr(organization, 'twilio_whatsapp_number', None) or getattr(settings, 'TWILIO_WHATSAPP_NUMBER', None)
    
    return {
        'account_sid': account_sid,
        'auth_token': auth_token,
        'phone_number': phone_number,
        'whatsapp_number': whatsapp_number
    }


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


def prepare_sms_content(event, recipient_name=None, is_anonymous=False):
    """Prepare SMS content with length limits in mind"""
    # Basic message
    message_body = f"""
🎉 {f"Hi {recipient_name}! " if recipient_name and is_anonymous else ""}New Event: {event.title}

📅 {event.date_time.strftime('%b %d, %Y at %I:%M %p')}
📍 {(event.location or 'TBD')[:30]}

From: {event.organization.name}

Details: {settings.SITE_URL}/events/{event.id}/

Reply STOP to unsubscribe
    """.strip()

    # Ensure SMS doesn't exceed typical length limits
    if len(message_body) > 160:
        message_body = f"""
🎉 {recipient_name + ": " if recipient_name else ""}{event.title}
📅 {event.date_time.strftime('%b %d at %I:%M %p')}
From: {event.organization.name}
{settings.SITE_URL}/events/{event.id}/
        """.strip()
    
    return message_body


def prepare_whatsapp_content(event, recipient_name=None, is_anonymous=False, respond_url=None, availability_url=None):
    """Prepare WhatsApp content"""
    description = event.description[:100] + '...' if event.description and len(event.description) > 100 else (
            event.description or '')
    
    # Base message
    message_body = f"""
🎉 {"Hi *" + recipient_name + "*! " if recipient_name and is_anonymous else ""}*New Event from {event.organization.name}*

📅 *{event.title}*
🗓️ {event.date_time.strftime('%B %d, %Y at %I:%M %p')}
📍 {event.location or 'Location TBD'}

{description}

🔗 View details: {settings.SITE_URL}/events/{event.id}/
    """.strip()
    
    # Add respond URL if provided
    if respond_url:
        message_body += f"\n✅ Respond: {respond_url}"
    
    # Add availability URL if provided
    if availability_url:
        message_body += f"\n⚙️ Update availability: {availability_url}"
    
    # Add create account message for anonymous users
    if is_anonymous:
        message_body += f"\n\n💡 _Create a free account for more features!_"
    
    return message_body


def send_sms(client, from_phone, to_phone, message_body):
    """Send SMS using Twilio client"""
    return client.messages.create(
        body=message_body,
        from_=from_phone,
        to=to_phone
    )


def send_whatsapp(client, from_whatsapp, to_phone, message_body):
    """Send WhatsApp message using Twilio client"""
    return client.messages.create(
        body=message_body,
        from_=from_whatsapp,
        to=f"whatsapp:{to_phone}"
    )
# notifications/tasks.py
import logging

from celery import shared_task
from django.conf import settings
from django.template.loader import render_to_string

# Import Twilio only if available
try:
    from twilio.rest import Client
    from twilio.base.exceptions import TwilioException

    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    TwilioException = Exception

logger = logging.getLogger(__name__)


@shared_task(bind=True, retry_backoff=True, max_retries=3)
def send_event_notifications(self, event_id, notification_type='creation'):
    """Send notifications for event creation or deletion"""
    from events.models import Event
    from organizations.models import Subscription, AnonymousSubscription

    try:
        event = Event.objects.get(id=event_id)
    except Event.DoesNotExist:
        logger.error(f"Event {event_id} not found")
        return 0

    organization = event.organization
    notifications_sent = 0

    # Template selection based on notification type
    if notification_type == 'deletion':
        email_template = 'notifications/email/event_deletion.html'
        sms_template = 'notifications/sms/event_deletion.txt'
        whatsapp_template = 'notifications/whatsapp/event_deletion.txt'
        subject_prefix = 'Event Cancelled'
    else:
        email_template = 'notifications/email/event_notification.html'
        sms_template = 'notifications/sms/event_notification.txt'
        whatsapp_template = 'notifications/whatsapp/event_notification.txt'
        subject_prefix = 'New Event'

    # Get all subscribers
    regular_subscribers = Subscription.objects.filter(organization=organization)
    anonymous_subscribers = AnonymousSubscription.objects.filter(organization=organization)

    # Process regular subscribers
    for subscription in regular_subscribers:
        user = subscription.user
        should_notify = _should_notify_user(subscription, event, notification_type)

        if should_notify:
            context = _get_notification_context(event, organization, user.username, user.email)
            _send_notification(organization, user.email, user.phone_number, user.whatsapp_number,
                               email_template, sms_template, whatsapp_template, context, subject_prefix)
            notifications_sent += 1

    # Process anonymous subscribers
    for anon_subscription in anonymous_subscribers:
        should_notify = _should_notify_anonymous(anon_subscription, event, notification_type)

        if should_notify:
            context = _get_notification_context(event, organization,
                                                anon_subscription.name, anon_subscription.email,
                                                is_anonymous=True)
            _send_notification(organization, anon_subscription.email,
                               anon_subscription.phone_number, anon_subscription.whatsapp_number,
                               email_template, sms_template, whatsapp_template, context, subject_prefix)
            notifications_sent += 1

    logger.info(f"Sent {notifications_sent} notifications for event {event_id}")
    return notifications_sent


def _should_notify_user(subscription, event, notification_type):
    """Determine if user should be notified."""
    if notification_type == 'deletion':
        return event.notify_on_deletion  # Always notify for deletions

    if subscription.notification_preference == 'all':
        return True

    elif subscription.notification_preference == 'matching':
        # Check if user's availability matches event time
        try:
            from accounts.services.availability_service import AvailabilityService
            return AvailabilityService.user_matches_event(subscription.user, event)
        except:
            return True  # Fallback to notify if availability check fails

    return False


def _should_notify_anonymous(anon_subscription, event, notification_type):
    """Determine if anonymous user should be notified."""
    if notification_type == 'deletion':
        return event.notify_on_deletion

    if anon_subscription.notification_preference == 'all':
        return True
    elif anon_subscription.notification_preference == 'matching':
        # Check if anonymous user's availability matches event time
        try:
            from accounts.services.availability_service import AvailabilityService
            return AvailabilityService.anonymous_matches_event(anon_subscription, event)
        except:
            return True  # Fallback to notify if availability check fails

    return False


def _get_notification_context(event, organization, recipient_name, recipient_email, is_anonymous=False):
    """Get context for notification templates."""
    return {
        'event': event,
        'organization': organization,
        'recipient_name': recipient_name,
        'recipient_email': recipient_email,
        'is_anonymous': is_anonymous,
        'event_url': f"{settings.SITE_URL}/{organization.user.username}/events/{event.slug}/",
        'respond_url': f"{settings.SITE_URL}/{organization.user.username}/events/{event.slug}/respond/",
        'unsubscribe_url': f"{settings.SITE_URL}/organizations/{organization.user.username}/unsubscribe/",
    }


def _send_notification(organization, email, phone_number, whatsapp_number,
                       email_template, sms_template, whatsapp_template, context, subject_prefix):
    """Send notification via configured method."""
    try:
        if organization.notification_type == 'email':
            _send_email_notification(email, email_template, context, subject_prefix)
        elif organization.notification_type == 'sms' and phone_number:
            _send_sms_notification(organization, phone_number, sms_template, context)
        elif organization.notification_type == 'whatsapp' and whatsapp_number:
            _send_whatsapp_notification(organization, whatsapp_number, whatsapp_template, context)
    except Exception as e:
        logger.error(f"Failed to send notification: {str(e)}")


def _send_email_notification(email, template, context, subject_prefix):
    """Send email notification."""
    from django.core.mail import send_mail

    html_content = render_to_string(template, context)
    subject = f"{subject_prefix}: {context['event'].title}"

    send_mail(
        subject=subject,
        message="",  # Plain text version can be added if needed
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        html_message=html_content,
        fail_silently=False,
    )


def _send_sms_notification(organization, phone_number, sms_template, context):
    """Send SMS notification using template."""
    if not TWILIO_AVAILABLE:
        logger.error("Twilio is not installed. Install with: pip install twilio")
        return False

    # Get Twilio credentials
    account_sid = getattr(organization, 'twilio_account_sid', None) or getattr(settings, 'TWILIO_ACCOUNT_SID', None)
    auth_token = getattr(organization, 'twilio_auth_token', None) or getattr(settings, 'TWILIO_AUTH_TOKEN', None)
    from_phone = getattr(organization, 'twilio_phone_number', None) or getattr(settings, 'TWILIO_PHONE_NUMBER', None)

    if not all([account_sid, auth_token, from_phone]):
        logger.error("Twilio SMS credentials not configured")
        return False

    try:
        client = Client(account_sid, auth_token)

        # Render SMS content from template
        message_body = render_to_string(sms_template, context).strip()

        client.messages.create(
            body=message_body,
            from_=from_phone,
            to=phone_number
        )
        return True

    except TwilioException as e:
        logger.error(f"Twilio SMS error: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"SMS sending error: {str(e)}")
        return False


def _send_whatsapp_notification(organization, whatsapp_number, whatsapp_template, context):
    """Send WhatsApp notification using template."""
    if not TWILIO_AVAILABLE:
        logger.error("Twilio is not installed. Install with: pip install twilio")
        return False

    # Get Twilio credentials
    account_sid = getattr(organization, 'twilio_account_sid', None) or getattr(settings, 'TWILIO_ACCOUNT_SID', None)
    auth_token = getattr(organization, 'twilio_auth_token', None) or getattr(settings, 'TWILIO_AUTH_TOKEN', None)
    from_whatsapp = getattr(organization, 'twilio_whatsapp_number', None) or getattr(settings, 'TWILIO_WHATSAPP_NUMBER',
                                                                                     None)

    if not all([account_sid, auth_token, from_whatsapp]):
        logger.error("Twilio WhatsApp credentials not configured")
        return False

    try:
        client = Client(account_sid, auth_token)

        # Render WhatsApp content from template
        message_body = render_to_string(whatsapp_template, context).strip()

        client.messages.create(
            body=message_body,
            from_=from_whatsapp,
            to=f"whatsapp:{whatsapp_number}"
        )
        return True

    except TwilioException as e:
        logger.error(f"Twilio WhatsApp error: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"WhatsApp sending error: {str(e)}")
        return False

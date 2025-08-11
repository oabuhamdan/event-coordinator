from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import logging

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
def send_event_notifications(self, event_id):
    """Send notifications for a new event to all relevant subscribers"""
    from events.models import Event
    from organizations.models import Subscription, AnonymousSubscription

    try:
        event = Event.objects.get(id=event_id)
    except Event.DoesNotExist:
        logger.error(f"Event {event_id} not found")
        return 0

    organization = event.organization
    notifications_sent = 0

    # Get all regular subscribers
    regular_subscribers = Subscription.objects.filter(organization=organization)

    # Get all anonymous subscribers
    anonymous_subscribers = AnonymousSubscription.objects.filter(organization=organization)

    # Process regular subscribers
    for subscription in regular_subscribers:
        user = subscription.user

        # Check notification preference
        should_notify = False

        if subscription.notification_preference == 'all':
            should_notify = True
        elif subscription.notification_preference == 'matching':
            # Check if event matches user's availability
            should_notify = event.matches_user_availability(user)

        if should_notify:
            # Send notification based on organization's preferred method
            try:
                if organization.notification_type == 'email':
                    send_email_notification.delay(event_id, user_id=user.id)
                elif organization.notification_type == 'sms':
                    send_sms_notification.delay(event_id, user_id=user.id)
                elif organization.notification_type == 'whatsapp':
                    send_whatsapp_notification.delay(event_id, user_id=user.id)

                notifications_sent += 1
            except Exception as e:
                logger.error(f"Failed to queue notification for user {user.id}: {e}")

    # Process anonymous subscribers
    for anon_subscription in anonymous_subscribers:
        # Check notification preference
        should_notify = False

        if anon_subscription.notification_preference == 'all':
            should_notify = True
        elif anon_subscription.notification_preference == 'matching':
            # Check if event matches anonymous user's availability
            should_notify = event.matches_anonymous_availability(anon_subscription)

        if should_notify:
            # Send notification based on organization's preferred method
            try:
                if organization.notification_type == 'email':
                    send_anonymous_email_notification.delay(event_id, anon_subscription_id=anon_subscription.id)
                elif organization.notification_type == 'sms' and anon_subscription.phone_number:
                    send_anonymous_sms_notification.delay(event_id, anon_subscription_id=anon_subscription.id)
                elif organization.notification_type == 'whatsapp' and anon_subscription.whatsapp_number:
                    send_anonymous_whatsapp_notification.delay(event_id, anon_subscription_id=anon_subscription.id)

                notifications_sent += 1
            except Exception as e:
                logger.error(f"Failed to queue notification for anonymous subscription {anon_subscription.id}: {e}")

    logger.info(f"Queued {notifications_sent} notifications for event {event_id}")
    return notifications_sent


@shared_task(bind=True, retry_backoff=True, max_retries=3)
def send_email_notification(self, event_id, user_id):
    """Send email notification to a registered user"""
    from events.models import Event, NotificationLog
    from django.contrib.auth import get_user_model

    User = get_user_model()

    try:
        event = Event.objects.get(id=event_id)
        user = User.objects.get(id=user_id)
    except (Event.DoesNotExist, User.DoesNotExist) as e:
        logger.error(f"Error in send_email_notification: {e}")
        return False

    try:
        # Check if event matches user availability for template context
        matches_availability = event.matches_user_availability(user)

        # Prepare email content
        context = {
            'event': event,
            'user': user,
            'user_name': user.get_full_name() or user.username,
            'organization': event.organization,
            'event_url': f"{settings.SITE_URL}/events/{event.id}/",
            'respond_url': f"{settings.SITE_URL}/events/{event.id}/respond/",
            'availability_url': f"{settings.SITE_URL}/events/availability/{event.organization.id}/",
            'unsubscribe_url': f"{settings.SITE_URL}/organizations/{event.organization.id}/unsubscribe/",
            'matches_availability': matches_availability,
        }

        # Render email templates
        try:
            html_message = render_to_string('notifications/email/event_notification.html', context)
            text_message = strip_tags(html_message)
        except Exception as e:
            logger.warning(f"Could not render custom template, using fallback: {e}")
            # Fallback to simple text email
            html_message = None
            text_message = f"""
New Event: {event.title}

Organization: {event.organization.name}
Date: {event.date_time.strftime('%B %d, %Y at %I:%M %p')}
Location: {event.location or 'TBD'}

View details: {context['event_url']}
Respond: {context['respond_url']}

Best regards,
{event.organization.name}
            """.strip()

        subject = f"New Event: {event.title} - {event.organization.name}"

        # Send email
        send_mail(
            subject=subject,
            message=text_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )

        # Log successful notification
        NotificationLog.objects.create(
            event=event,
            user=user,
            notification_type='email',
            success=True
        )

        logger.info(f"Email sent successfully to {user.email} for event {event_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email to {user.email} for event {event_id}: {e}")

        # Log failed notification
        NotificationLog.objects.create(
            event=event,
            user=user,
            notification_type='email',
            success=False,
            error_message=str(e)
        )

        # Retry the task
        raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))


@shared_task(bind=True, retry_backoff=True, max_retries=3)
def send_anonymous_email_notification(self, event_id, anon_subscription_id):
    """Send email notification to an anonymous subscriber"""
    from events.models import Event, NotificationLog
    from organizations.models import AnonymousSubscription

    try:
        event = Event.objects.get(id=event_id)
        anon_subscription = AnonymousSubscription.objects.get(id=anon_subscription_id)
    except (Event.DoesNotExist, AnonymousSubscription.DoesNotExist) as e:
        logger.error(f"Error in send_anonymous_email_notification: {e}")
        return False

    try:
        # Prepare email content
        context = {
            'event': event,
            'subscriber_name': anon_subscription.name,
            'organization': event.organization,
            'event_url': f"{settings.SITE_URL}/events/{event.id}/",
            'availability_url': f"{settings.SITE_URL}/events/availability/{event.organization.id}/{anon_subscription.id}/anonymous/",
            'create_account_url': f"{settings.SITE_URL}/accounts/register/",
        }

        # Render email templates
        try:
            html_message = render_to_string('notifications/email/anonymous_event_notification.html', context)
            text_message = strip_tags(html_message)
        except Exception as e:
            logger.warning(f"Could not render custom template, using fallback: {e}")
            # Fallback to simple text email
            html_message = None
            text_message = f"""
Hi {anon_subscription.name},

New Event: {event.title}

Organization: {event.organization.name}
Date: {event.date_time.strftime('%B %d, %Y at %I:%M %p')}
Location: {event.location or 'TBD'}

View details: {context['event_url']}
Update availability: {context['availability_url']}

Best regards,
{event.organization.name}
            """.strip()

        subject = f"New Event: {event.title} - {event.organization.name}"

        # Send email
        send_mail(
            subject=subject,
            message=text_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[anon_subscription.email],
            html_message=html_message,
            fail_silently=False,
        )

        # Log successful notification
        NotificationLog.objects.create(
            event=event,
            user=None,
            notification_type='email',
            success=True,
            error_message=f"Anonymous subscriber: {anon_subscription.name} ({anon_subscription.email})"
        )

        logger.info(f"Email sent successfully to anonymous subscriber {anon_subscription.email} for event {event_id}")
        return True

    except Exception as e:
        logger.error(
            f"Failed to send email to anonymous subscriber {anon_subscription.email} for event {event_id}: {e}")

        # Log failed notification
        NotificationLog.objects.create(
            event=event,
            user=None,
            notification_type='email',
            success=False,
            error_message=f"Anonymous subscriber: {anon_subscription.name} ({anon_subscription.email}) - Error: {str(e)}"
        )

        # Retry the task
        raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))


@shared_task(bind=True, retry_backoff=True, max_retries=3)
def send_sms_notification(self, event_id, user_id):
    """Send SMS notification to a registered user"""
    from events.models import Event, NotificationLog
    from django.contrib.auth import get_user_model

    if not TWILIO_AVAILABLE:
        logger.error("Twilio is not installed. Install with: pip install twilio")
        return False

    User = get_user_model()

    try:
        event = Event.objects.get(id=event_id)
        user = User.objects.get(id=user_id)
    except (Event.DoesNotExist, User.DoesNotExist) as e:
        logger.error(f"Error in send_sms_notification: {e}")
        return False

    if not user.phone_number:
        logger.warning(f"User {user.id} has no phone number for SMS notification")
        return False

    try:
        # Get organization's Twilio settings or fall back to global settings
        org = event.organization
        account_sid = getattr(org, 'twilio_account_sid', None) or getattr(settings, 'TWILIO_ACCOUNT_SID', None)
        auth_token = getattr(org, 'twilio_auth_token', None) or getattr(settings, 'TWILIO_AUTH_TOKEN', None)
        from_phone = getattr(org, 'twilio_phone_number', None) or getattr(settings, 'TWILIO_PHONE_NUMBER', None)

        if not all([account_sid, auth_token, from_phone]):
            raise Exception("Twilio credentials not configured")

        client = Client(account_sid, auth_token)

        # Prepare SMS content (keep it short for SMS)
        message_body = f"""
🎉 New Event: {event.title}

📅 {event.date_time.strftime('%b %d, %Y at %I:%M %p')}
📍 {(event.location or 'TBD')[:30]}

From: {event.organization.name}

Details: {settings.SITE_URL}/events/{event.id}/

Reply STOP to unsubscribe
        """.strip()

        # Ensure SMS doesn't exceed typical length limits
        if len(message_body) > 160:
            message_body = f"""
🎉 {event.title}
📅 {event.date_time.strftime('%b %d at %I:%M %p')}
From: {event.organization.name}
{settings.SITE_URL}/events/{event.id}/
            """.strip()

        # Send SMS
        message = client.messages.create(
            body=message_body,
            from_=from_phone,
            to=user.phone_number
        )

        # Log successful notification
        NotificationLog.objects.create(
            event=event,
            user=user,
            notification_type='sms',
            success=True
        )

        logger.info(f"SMS sent successfully to {user.phone_number} for event {event_id}")
        return True

    except TwilioException as e:
        logger.error(f"Twilio error sending SMS to {user.phone_number} for event {event_id}: {e}")

        # Log failed notification
        NotificationLog.objects.create(
            event=event,
            user=user,
            notification_type='sms',
            success=False,
            error_message=str(e)
        )

        # Don't retry on Twilio errors (usually config issues)
        return False

    except Exception as e:
        logger.error(f"Failed to send SMS to {user.phone_number} for event {event_id}: {e}")

        # Log failed notification
        NotificationLog.objects.create(
            event=event,
            user=user,
            notification_type='sms',
            success=False,
            error_message=str(e)
        )

        # Retry the task
        raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))


@shared_task(bind=True, retry_backoff=True, max_retries=3)
def send_anonymous_sms_notification(self, event_id, anon_subscription_id):
    """Send SMS notification to an anonymous subscriber"""
    from events.models import Event, NotificationLog
    from organizations.models import AnonymousSubscription

    if not TWILIO_AVAILABLE:
        logger.error("Twilio is not installed. Install with: pip install twilio")
        return False

    try:
        event = Event.objects.get(id=event_id)
        anon_subscription = AnonymousSubscription.objects.get(id=anon_subscription_id)
    except (Event.DoesNotExist, AnonymousSubscription.DoesNotExist) as e:
        logger.error(f"Error in send_anonymous_sms_notification: {e}")
        return False

    if not anon_subscription.phone_number:
        logger.warning(f"Anonymous subscription {anon_subscription_id} has no phone number for SMS")
        return False

    try:
        # Get organization's Twilio settings or fall back to global settings
        org = event.organization
        account_sid = getattr(org, 'twilio_account_sid', None) or getattr(settings, 'TWILIO_ACCOUNT_SID', None)
        auth_token = getattr(org, 'twilio_auth_token', None) or getattr(settings, 'TWILIO_AUTH_TOKEN', None)
        from_phone = getattr(org, 'twilio_phone_number', None) or getattr(settings, 'TWILIO_PHONE_NUMBER', None)

        if not all([account_sid, auth_token, from_phone]):
            raise Exception("Twilio credentials not configured")

        client = Client(account_sid, auth_token)

        # Prepare SMS content
        message_body = f"""
🎉 Hi {anon_subscription.name}! New Event: {event.title}

📅 {event.date_time.strftime('%b %d, %Y at %I:%M %p')}
📍 {(event.location or 'TBD')[:20]}

From: {event.organization.name}

Details: {settings.SITE_URL}/events/{event.id}/
        """.strip()

        # Ensure SMS doesn't exceed length limits
        if len(message_body) > 160:
            message_body = f"""
🎉 {anon_subscription.name}: {event.title}
📅 {event.date_time.strftime('%b %d at %I:%M %p')}
From: {event.organization.name}
{settings.SITE_URL}/events/{event.id}/
            """.strip()

        # Send SMS
        message = client.messages.create(
            body=message_body,
            from_=from_phone,
            to=anon_subscription.phone_number
        )

        # Log successful notification
        NotificationLog.objects.create(
            event=event,
            user=None,
            notification_type='sms',
            success=True,
            error_message=f"Anonymous subscriber: {anon_subscription.name} ({anon_subscription.phone_number})"
        )

        logger.info(
            f"SMS sent successfully to anonymous subscriber {anon_subscription.phone_number} for event {event_id}")
        return True

    except TwilioException as e:
        logger.error(
            f"Twilio error sending SMS to anonymous subscriber {anon_subscription.phone_number} for event {event_id}: {e}")

        # Log failed notification
        NotificationLog.objects.create(
            event=event,
            user=None,
            notification_type='sms',
            success=False,
            error_message=f"Anonymous subscriber: {anon_subscription.name} ({anon_subscription.phone_number}) - Error: {str(e)}"
        )

        # Don't retry on Twilio errors
        return False

    except Exception as e:
        logger.error(
            f"Failed to send SMS to anonymous subscriber {anon_subscription.phone_number} for event {event_id}: {e}")

        # Log failed notification
        NotificationLog.objects.create(
            event=event,
            user=None,
            notification_type='sms',
            success=False,
            error_message=f"Anonymous subscriber: {anon_subscription.name} ({anon_subscription.phone_number}) - Error: {str(e)}"
        )

        # Retry the task
        raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))


@shared_task(bind=True, retry_backoff=True, max_retries=3)
def send_whatsapp_notification(self, event_id, user_id):
    """Send WhatsApp notification to a registered user"""
    from events.models import Event, NotificationLog
    from django.contrib.auth import get_user_model

    if not TWILIO_AVAILABLE:
        logger.error("Twilio is not installed. Install with: pip install twilio")
        return False

    User = get_user_model()

    try:
        event = Event.objects.get(id=event_id)
        user = User.objects.get(id=user_id)
    except (Event.DoesNotExist, User.DoesNotExist) as e:
        logger.error(f"Error in send_whatsapp_notification: {e}")
        return False

    if not user.phone_number:
        logger.warning(f"User {user.id} has no phone number for WhatsApp notification")
        return False

    try:
        # Get organization's Twilio settings or fall back to global settings
        org = event.organization
        account_sid = getattr(org, 'twilio_account_sid', None) or getattr(settings, 'TWILIO_ACCOUNT_SID', None)
        auth_token = getattr(org, 'twilio_auth_token', None) or getattr(settings, 'TWILIO_AUTH_TOKEN', None)
        from_whatsapp = getattr(org, 'twilio_whatsapp_number', None) or getattr(settings, 'TWILIO_WHATSAPP_NUMBER',
                                                                                None)

        if not all([account_sid, auth_token, from_whatsapp]):
            raise Exception("Twilio WhatsApp credentials not configured")

        client = Client(account_sid, auth_token)

        # Prepare WhatsApp content (can be longer than SMS)
        description = event.description[:100] + '...' if event.description and len(event.description) > 100 else (
                event.description or '')

        message_body = f"""
🎉 *New Event from {event.organization.name}*

📅 *{event.title}*
🗓️ {event.date_time.strftime('%B %d, %Y at %I:%M %p')}
📍 {event.location or 'Location TBD'}

{description}

🔗 View details: {settings.SITE_URL}/events/{event.id}/
✅ Respond: {settings.SITE_URL}/events/{event.id}/respond/
        """.strip()

        # Send WhatsApp message
        message = client.messages.create(
            body=message_body,
            from_=from_whatsapp,
            to=f"whatsapp:{user.phone_number}"
        )

        # Log successful notification
        NotificationLog.objects.create(
            event=event,
            user=user,
            notification_type='whatsapp',
            success=True
        )

        logger.info(f"WhatsApp sent successfully to {user.phone_number} for event {event_id}")
        return True

    except TwilioException as e:
        logger.error(f"Twilio error sending WhatsApp to {user.phone_number} for event {event_id}: {e}")

        # Log failed notification
        NotificationLog.objects.create(
            event=event,
            user=user,
            notification_type='whatsapp',
            success=False,
            error_message=str(e)
        )

        # Don't retry on Twilio errors
        return False

    except Exception as e:
        logger.error(f"Failed to send WhatsApp to {user.phone_number} for event {event_id}: {e}")

        # Log failed notification
        NotificationLog.objects.create(
            event=event,
            user=user,
            notification_type='whatsapp',
            success=False,
            error_message=str(e)
        )

        # Retry the task
        raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))


@shared_task(bind=True, retry_backoff=True, max_retries=3)
def send_anonymous_whatsapp_notification(self, event_id, anon_subscription_id):
    """Send WhatsApp notification to an anonymous subscriber"""
    from events.models import Event, NotificationLog
    from organizations.models import AnonymousSubscription

    if not TWILIO_AVAILABLE:
        logger.error("Twilio is not installed. Install with: pip install twilio")
        return False

    try:
        event = Event.objects.get(id=event_id)
        anon_subscription = AnonymousSubscription.objects.get(id=anon_subscription_id)
    except (Event.DoesNotExist, AnonymousSubscription.DoesNotExist) as e:
        logger.error(f"Error in send_anonymous_whatsapp_notification: {e}")
        return False

    if not anon_subscription.whatsapp_number:
        logger.warning(f"Anonymous subscription {anon_subscription_id} has no WhatsApp number")
        return False

    try:
        # Get organization's Twilio settings or fall back to global settings
        org = event.organization
        account_sid = getattr(org, 'twilio_account_sid', None) or getattr(settings, 'TWILIO_ACCOUNT_SID', None)
        auth_token = getattr(org, 'twilio_auth_token', None) or getattr(settings, 'TWILIO_AUTH_TOKEN', None)
        from_whatsapp = getattr(org, 'twilio_whatsapp_number', None) or getattr(settings, 'TWILIO_WHATSAPP_NUMBER',
                                                                                None)

        if not all([account_sid, auth_token, from_whatsapp]):
            raise Exception("Twilio WhatsApp credentials not configured")

        client = Client(account_sid, auth_token)

        # Prepare WhatsApp content
        description = event.description[:100] + '...' if event.description and len(event.description) > 100 else (
                event.description or '')

        message_body = f"""
🎉 Hi *{anon_subscription.name}*! New Event from *{event.organization.name}*

📅 *{event.title}*
🗓️ {event.date_time.strftime('%B %d, %Y at %I:%M %p')}
📍 {event.location or 'Location TBD'}

{description}

🔗 View details: {settings.SITE_URL}/events/{event.id}/
⚙️ Update availability: {settings.SITE_URL}/events/availability/{event.organization.id}/{anon_subscription.id}/anonymous/

💡 _Create a free account for more features!_
        """.strip()

        # Send WhatsApp message
        message = client.messages.create(
            body=message_body,
            from_=from_whatsapp,
            to=f"whatsapp:{anon_subscription.whatsapp_number}"
        )

        # Log successful notification
        NotificationLog.objects.create(
            event=event,
            user=None,
            notification_type='whatsapp',
            success=True,
            error_message=f"Anonymous subscriber: {anon_subscription.name} ({anon_subscription.whatsapp_number})"
        )

        logger.info(
            f"WhatsApp sent successfully to anonymous subscriber {anon_subscription.whatsapp_number} for event {event_id}")
        return True

    except TwilioException as e:
        logger.error(
            f"Twilio error sending WhatsApp to anonymous subscriber {anon_subscription.whatsapp_number} for event {event_id}: {e}")

        # Log failed notification
        NotificationLog.objects.create(
            event=event,
            user=None,
            notification_type='whatsapp',
            success=False,
            error_message=f"Anonymous subscriber: {anon_subscription.name} ({anon_subscription.whatsapp_number}) - Error: {str(e)}"
        )

        # Don't retry on Twilio errors
        return False

    except Exception as e:
        logger.error(
            f"Failed to send WhatsApp to anonymous subscriber {anon_subscription.whatsapp_number} for event {event_id}: {e}")

        # Log failed notification
        NotificationLog.objects.create(
            event=event,
            user=None,
            notification_type='whatsapp',
            success=False,
            error_message=f"Anonymous subscriber: {anon_subscription.name} ({anon_subscription.whatsapp_number}) - Error: {str(e)}"
        )

        # Retry the task
        raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))

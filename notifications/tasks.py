import logging
from celery import shared_task
from django.conf import settings
from django.utils import timezone

# Import Twilio only if available
try:
    from twilio.rest import Client
    from twilio.base.exceptions import TwilioException
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    TwilioException = Exception
    Client = None

logger = logging.getLogger(__name__)


@shared_task(bind=True, retry_backoff=True, max_retries=3)
def send_event_notifications(self, event_id):
    """Send notifications for a new event to all relevant subscribers"""
    from events.models import Event
    from events.services import AvailabilityService
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
            # Use service layer for availability checking
            should_notify = AvailabilityService.user_matches_event(user, event)

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
            # Use service layer for availability checking
            should_notify = AvailabilityService.anonymous_matches_event(anon_subscription, event)

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
    from events.models import Event
    from events.services import AvailabilityService
    from django.contrib.auth import get_user_model
    from notifications.utils import render_email_template, send_email, log_notification

    User = get_user_model()

    try:
        event = Event.objects.get(id=event_id)
        user = User.objects.get(id=user_id)
    except (Event.DoesNotExist, User.DoesNotExist) as e:
        logger.error(f"Error in send_email_notification: {e}")
        return False

    try:
        # Use service layer for availability checking
        matches_availability = AvailabilityService.user_matches_event(user, event)

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

        # Fallback text for email
        fallback_text = f"""
New Event: {event.title}

Organization: {event.organization.name}
Date: {event.date_time.strftime('%B %d, %Y at %I:%M %p')}
Location: {event.location or 'TBD'}

View details: {context['event_url']}
Respond: {context['respond_url']}

Best regards,
{event.organization.name}
        """.strip()

        # Render email template
        email_content = render_email_template(
            'notifications/email/event_notification.html', 
            context, 
            fallback_text
        )

        subject = f"New Event: {event.title} - {event.organization.name}"

        # Send email
        send_email(
            recipient_email=user.email,
            subject=subject,
            text_message=email_content['text_message'],
            html_message=email_content['html_message']
        )

        # Log successful notification
        log_notification(
            event=event,
            user=user,
            notification_type='email',
            success=True
        )

        return True

    except Exception as e:
        # Log failed notification
        log_notification(
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
    from events.models import Event
    from organizations.models import AnonymousSubscription
    from notifications.utils import render_email_template, send_email, log_notification

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

        # Fallback text for email
        fallback_text = f"""
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

        # Render email template
        email_content = render_email_template(
            'notifications/email/anonymous_event_notification.html', 
            context, 
            fallback_text
        )

        subject = f"New Event: {event.title} - {event.organization.name}"

        # Send email
        send_email(
            recipient_email=anon_subscription.email,
            subject=subject,
            text_message=email_content['text_message'],
            html_message=email_content['html_message']
        )

        # Log successful notification
        log_notification(
            event=event,
            anonymous_subscription=anon_subscription,
            notification_type='email',
            success=True
        )

        return True

    except Exception as e:
        # Log failed notification
        log_notification(
            event=event,
            anonymous_subscription=anon_subscription,
            notification_type='email',
            success=False,
            error_message=str(e)
        )

        # Retry the task
        raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))


@shared_task(bind=True, retry_backoff=True, max_retries=3)
def send_sms_notification(self, event_id, user_id):
    """Send SMS notification to a registered user"""
    from events.models import Event
    from django.contrib.auth import get_user_model
    from notifications.utils import get_twilio_credentials, prepare_sms_content, send_sms, log_notification

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
        # Get Twilio credentials
        credentials = get_twilio_credentials(event.organization)
        
        if not all([credentials['account_sid'], credentials['auth_token'], credentials['phone_number']]):
            raise Exception("Twilio credentials not configured")

        # Create Twilio client
        client = Client(credentials['account_sid'], credentials['auth_token'])

        # Prepare SMS content
        message_body = prepare_sms_content(event)

        # Send SMS
        send_sms(
            client=client,
            from_phone=credentials['phone_number'],
            to_phone=user.phone_number,
            message_body=message_body
        )

        # Log successful notification
        log_notification(
            event=event,
            user=user,
            notification_type='sms',
            success=True
        )

        return True

    except TwilioException as e:
        # Log failed notification
        log_notification(
            event=event,
            user=user,
            notification_type='sms',
            success=False,
            error_message=f"Twilio error: {str(e)}"
        )

        # Don't retry on Twilio errors (usually config issues)
        return False

    except Exception as e:
        # Log failed notification
        log_notification(
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
    from events.models import Event
    from organizations.models import AnonymousSubscription
    from notifications.utils import get_twilio_credentials, prepare_sms_content, send_sms, log_notification

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
        # Get Twilio credentials
        credentials = get_twilio_credentials(event.organization)
        
        if not all([credentials['account_sid'], credentials['auth_token'], credentials['phone_number']]):
            raise Exception("Twilio credentials not configured")

        # Create Twilio client
        client = Client(credentials['account_sid'], credentials['auth_token'])

        # Prepare SMS content
        message_body = prepare_sms_content(
            event=event,
            recipient_name=anon_subscription.name,
            is_anonymous=True
        )

        # Send SMS
        send_sms(
            client=client,
            from_phone=credentials['phone_number'],
            to_phone=anon_subscription.phone_number,
            message_body=message_body
        )

        # Log successful notification
        log_notification(
            event=event,
            anonymous_subscription=anon_subscription,
            notification_type='sms',
            success=True
        )

        return True

    except TwilioException as e:
        # Log failed notification
        log_notification(
            event=event,
            anonymous_subscription=anon_subscription,
            notification_type='sms',
            success=False,
            error_message=f"Twilio error: {str(e)}"
        )

        # Don't retry on Twilio errors
        return False

    except Exception as e:
        # Log failed notification
        log_notification(
            event=event,
            anonymous_subscription=anon_subscription,
            notification_type='sms',
            success=False,
            error_message=str(e)
        )

        # Retry the task
        raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))


@shared_task(bind=True, retry_backoff=True, max_retries=3)
def send_whatsapp_notification(self, event_id, user_id):
    """Send WhatsApp notification to a registered user"""
    from events.models import Event
    from django.contrib.auth import get_user_model
    from notifications.utils import get_twilio_credentials, prepare_whatsapp_content, send_whatsapp, log_notification

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
        # Get Twilio credentials
        credentials = get_twilio_credentials(event.organization)
        
        if not all([credentials['account_sid'], credentials['auth_token'], credentials['whatsapp_number']]):
            raise Exception("Twilio WhatsApp credentials not configured")

        # Create Twilio client
        client = Client(credentials['account_sid'], credentials['auth_token'])

        # Prepare WhatsApp content
        respond_url = f"{settings.SITE_URL}/events/{event.id}/respond/"
        message_body = prepare_whatsapp_content(
            event=event,
            respond_url=respond_url
        )

        # Send WhatsApp message
        send_whatsapp(
            client=client,
            from_whatsapp=credentials['whatsapp_number'],
            to_phone=user.phone_number,
            message_body=message_body
        )

        # Log successful notification
        log_notification(
            event=event,
            user=user,
            notification_type='whatsapp',
            success=True
        )

        return True

    except TwilioException as e:
        # Log failed notification
        log_notification(
            event=event,
            user=user,
            notification_type='whatsapp',
            success=False,
            error_message=f"Twilio error: {str(e)}"
        )

        # Don't retry on Twilio errors
        return False

    except Exception as e:
        # Log failed notification
        log_notification(
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
    from events.models import Event
    from organizations.models import AnonymousSubscription
    from notifications.utils import get_twilio_credentials, prepare_whatsapp_content, send_whatsapp, log_notification

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
        # Get Twilio credentials
        credentials = get_twilio_credentials(event.organization)
        
        if not all([credentials['account_sid'], credentials['auth_token'], credentials['whatsapp_number']]):
            raise Exception("Twilio WhatsApp credentials not configured")

        # Create Twilio client
        client = Client(credentials['account_sid'], credentials['auth_token'])

        # Prepare WhatsApp content
        availability_url = f"{settings.SITE_URL}/events/availability/{event.organization.id}/{anon_subscription.id}/anonymous/"
        message_body = prepare_whatsapp_content(
            event=event,
            recipient_name=anon_subscription.name,
            is_anonymous=True,
            availability_url=availability_url
        )

        # Send WhatsApp message
        send_whatsapp(
            client=client,
            from_whatsapp=credentials['whatsapp_number'],
            to_phone=anon_subscription.whatsapp_number,
            message_body=message_body
        )

        # Log successful notification
        log_notification(
            event=event,
            anonymous_subscription=anon_subscription,
            notification_type='whatsapp',
            success=True
        )

        return True

    except TwilioException as e:
        # Log failed notification
        log_notification(
            event=event,
            anonymous_subscription=anon_subscription,
            notification_type='whatsapp',
            success=False,
            error_message=f"Twilio error: {str(e)}"
        )

        # Don't retry on Twilio errors
        return False

    except Exception as e:
        # Log failed notification
        log_notification(
            event=event,
            anonymous_subscription=anon_subscription,
            notification_type='whatsapp',
            success=False,
            error_message=str(e)
        )

        # Retry the task
        raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))

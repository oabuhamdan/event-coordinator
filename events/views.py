# events/views.py - CLEANED VERSION
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.utils import timezone

from organizations.services import OrganizationService
from .models import Event, EventResponse
from .forms import EventForm, EventResponseForm
from .services import EventService, NotificationService
from accounts.utils import organization_required
from accounts.services.session_service import SessionService
from organizations.models import Organization, Subscription, AnonymousSubscription


@login_required
@organization_required
def create_event(request, username):
    """Create a new event - only for organizations."""
    organization = OrganizationService.get_organization_for_user(request.user)

    if request.method == 'POST':
        form = EventForm(request.POST)
        if form.is_valid():
            event = form.save(commit=False)
            event.organization = organization
            event.save()

            # Send notifications if enabled
            if event.notify_on_creation:
                try:
                    NotificationService.send_event_creation_notifications(event)
                    notification_message = "Notifications sent to"
                except Exception as e:
                    notification_message = "Available to"
                    messages.warning(request, f"Event created but notifications failed: {str(e)}")
            else:
                notification_message = "Available to"

            subscriber_count = (
                    organization.subscription_set.count() +
                    organization.anonymoussubscription_set.count()
            )

            messages.success(
                request,
                f'Event "{event.title}" created successfully! '
                f'{notification_message} {subscriber_count} subscribers.'
            )
            return redirect('events:detail', username=username, slug=event.slug)
        else:
            messages.error(request, 'Invalid form data. Please check the details.')
            print(form.errors)
    else:
        form = EventForm()

    # Get availability slots for suggestions
    try:
        availability_slots = organization.get_top_availability_slots()
    except Exception:
        availability_slots = []

    return render(request, 'events/create.html', {
        'form': form,
        'organization': organization,
        'availability_slots': availability_slots,
    })


@login_required
@organization_required
def edit_event(request, username, slug):
    """Edit an existing event."""
    organization = OrganizationService.get_organization_for_user(request.user)
    event = get_object_or_404(Event, organization=organization, slug=slug)

    if request.method == 'POST':
        form = EventForm(request.POST, instance=event)
        if form.is_valid():
            updated_event = form.save()
            messages.success(request, f'Event "{updated_event.title}" updated successfully!')
            return redirect('events:detail', username=username, slug=updated_event.slug)
    else:
        form = EventForm(instance=event)

    return render(request, 'events/edit.html', {
        'form': form,
        'event': event,
        'organization': organization,
    })


def list_events(request, username):
    """List all events for an organization with pagination."""
    organization = get_object_or_404(Organization, user__username=username)

    # Track session for anonymous users
    SessionService.track_session(request, request.user if request.user.is_authenticated else None)

    events = Event.objects.filter(organization=organization)

    # Filter by upcoming/past
    filter_type = request.GET.get('filter', 'upcoming')
    if filter_type == 'upcoming':
        events = events.filter(start_datetime__gte=timezone.now())
    elif filter_type == 'past':
        events = events.filter(end_datetime__lt=timezone.now())
    # 'all' shows everything

    events = events.order_by('-start_datetime')

    paginator = Paginator(events, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'events/list.html', {
        'page_obj': page_obj,
        'events': page_obj.object_list,
        'organization': organization,
        'filter_type': filter_type,
        'can_manage': (request.user.is_authenticated and
                       request.user.is_organization and
                       organization.user == request.user)
    })


def event_detail(request, username, slug):
    """Display event details and handle responses."""
    organization = get_object_or_404(Organization, user__username=username)
    event = get_object_or_404(Event, organization=organization, slug=slug)

    # Track session
    SessionService.track_session(request, request.user if request.user.is_authenticated else None)

    user_response = None
    can_respond = False

    if request.user.is_authenticated and request.user.is_regular_user:
        # Check if user is subscribed to this organization
        is_subscribed = Subscription.objects.filter(
            user=request.user,
            organization=organization
        ).exists()

        if is_subscribed:
            can_respond = True
            try:
                user_response = EventResponse.objects.get(event=event, user=request.user)
            except EventResponse.DoesNotExist:
                pass
    else:
        # Check anonymous subscription
        subscription_id = request.session.get(f'anonymous_subscription_{organization.pk}')
        if subscription_id:
            try:
                anonymous_subscription = AnonymousSubscription.objects.get(id=subscription_id)
                can_respond = True
                try:
                    user_response = EventResponse.objects.get(
                        event=event,
                        anonymous_subscription=anonymous_subscription
                    )
                except EventResponse.DoesNotExist:
                    pass
            except AnonymousSubscription.DoesNotExist:
                # Clean up invalid session data
                del request.session[f'anonymous_subscription_{organization.pk}']

    # Get response statistics
    response_counts = EventService.get_response_counts(event)

    context = {
        'event': event,
        'organization': organization,
        'user_response': user_response,
        'can_respond': can_respond and event.is_upcoming,
        'response_counts': response_counts,
        'can_manage': (request.user.is_authenticated and
                       request.user.is_organization and
                       organization.user == request.user)
    }

    return render(request, 'events/detail.html', context)


@login_required
@organization_required
def delete_event(request, username, slug):
    """Delete an event."""
    organization = OrganizationService.get_organization_for_user(request.user)
    event = get_object_or_404(Event, organization=organization, slug=slug)

    if request.method == 'POST':
        event_title = event.title

        # Send deletion notifications if enabled
        if event.notify_on_deletion:
            try:
                NotificationService.send_event_deletion_notifications(event)
                messages.info(request, f'Deletion notifications sent to subscribers.')
            except Exception as e:
                messages.warning(request, f'Event deleted but notifications failed: {str(e)}')

        event.delete()
        messages.success(request, f'Event "{event_title}" deleted successfully!')
        return redirect('organizations:dashboard')

    return render(request, 'events/delete.html', {
        'event': event,
        'organization': organization
    })


def respond_to_event(request, username, slug):
    """Handle event response from users."""
    organization = get_object_or_404(Organization, user__username=username)
    event = get_object_or_404(Event, organization=organization, slug=slug)

    # Check if event is still upcoming
    if not event.is_upcoming:
        messages.error(request, 'Cannot respond to past events.')
        return redirect('events:detail', username=username, slug=slug)

    # Determine user type and subscription status
    is_authenticated_user = request.user.is_authenticated and request.user.is_regular_user
    anonymous_subscription = None

    if is_authenticated_user:
        # Check if user is subscribed
        if not Subscription.objects.filter(user=request.user, organization=organization).exists():
            messages.error(request, 'You must be subscribed to this organization to respond to events.')
            return redirect('events:detail', username=username, slug=slug)
    else:
        # Check anonymous subscription
        subscription_id = request.session.get(f'anonymous_subscription_{organization.pk}')
        if subscription_id:
            try:
                anonymous_subscription = AnonymousSubscription.objects.get(id=subscription_id)
            except AnonymousSubscription.DoesNotExist:
                del request.session[f'anonymous_subscription_{organization.pk}']
                messages.error(request, 'Please subscribe to respond to events.')
                return redirect('events:detail', username=username, slug=slug)
        else:
            messages.error(request, 'Please subscribe to respond to events.')
            return redirect('events:detail', username=username, slug=slug)

    if request.method == 'POST':
        response_value = request.POST.get('response')

        if response_value not in ['yes', 'no', 'maybe']:
            messages.error(request, 'Invalid response.')
            return redirect('events:detail', username=username, slug=slug)

        try:
            if is_authenticated_user:
                response_obj, created = EventResponse.objects.update_or_create(
                    event=event,
                    user=request.user,
                    defaults={'response': response_value}
                )
            else:
                response_obj, created = EventResponse.objects.update_or_create(
                    event=event,
                    anonymous_subscription=anonymous_subscription,
                    defaults={'response': response_value}
                )

            action = "updated" if not created else "recorded"
            messages.success(request, f'Your response has been {action}!')

            # Handle AJAX requests
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                response_counts = EventService.get_response_counts(event)
                return JsonResponse({
                    'success': True,
                    'message': f'Response {action} successfully!',
                    'response_counts': response_counts
                })

        except Exception as e:
            messages.error(request, f'Error recording response: {str(e)}')

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': str(e)})

        return redirect('events:detail', username=username, slug=slug)

    # GET request - redirect to event detail
    return redirect('events:detail', username=username, slug=slug)


@login_required
@organization_required
def event_analytics(request, username, slug):
    """View analytics for a specific event."""
    organization = OrganizationService.get_organization_for_user(request.user)
    event = get_object_or_404(Event, organization=organization, slug=slug)

    response_counts = EventService.get_response_counts(event)
    responses = EventResponse.objects.filter(event=event).select_related('user', 'anonymous_subscription')

    # Separate responses by type

    context = {
        'event': event,
        'organization': organization,
        'response_counts': response_counts,
        'responses': responses,
        'total_responses': responses.count(),
    }

    return render(request, 'events/analytics.html', context)


def get_availability_slots(request, username):
    """API endpoint to get top availability slots for event creation."""
    organization = OrganizationService.get_organization_for_user(request.user)

    try:
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        limit = int(request.GET.get('limit', 3))

        slots = organization.get_top_availability_slots(
            limit=limit,
            start_date=start_date,
            end_date=end_date
        )
        return JsonResponse({'slots': slots})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

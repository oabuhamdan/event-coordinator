from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse

from .models import Event, EventResponse
from .forms import EventForm, EventResponseForm
from .services import EventService, EventQueryService
from .utils import can_user_manage_event
from accounts.utils import organization_required
from accounts.services.session_service import SessionService  # Fixed import
from organizations.models import Organization, Subscription, AnonymousSubscription


@login_required
@organization_required
def create_event(request):
    """Create a new event - only for organizations."""
    try:
        organization = request.user.organization
    except Organization.DoesNotExist:
        return redirect('organizations:create_profile')

    if request.method == 'POST':
        form = EventForm(request.POST)
        if form.is_valid():
            event_data = form.cleaned_data
            event = EventService.create_event(organization, event_data)

            subscriber_count = (
                organization.subscription_set.count() +
                organization.anonymoussubscription_set.count()
            )

            messages.success(
                request,
                f'Event "{event.title}" created successfully! '
                f'Notifications will be sent to {subscriber_count} subscribers.'
            )
            return redirect('events:detail', pk=event.pk)
    else:
        form = EventForm()

    return render(request, 'events/create.html', {
        'form': form,
        'organization': organization
    })


@login_required
@organization_required
def edit_event(request, pk):
    """Edit an existing event."""
    event = get_object_or_404(Event, pk=pk)

    if not can_user_manage_event(request.user, event):
        messages.error(request, 'You can only edit your own events.')
        return redirect('events:detail', pk=event.pk)

    if request.method == 'POST':
        form = EventForm(request.POST, instance=event)
        if form.is_valid():
            event_data = form.cleaned_data
            updated_event = EventService.update_event(event, event_data)
            messages.success(request, f'Event "{updated_event.title}" updated successfully!')
            return redirect('events:detail', pk=updated_event.pk)
    else:
        form = EventForm(instance=event)

    return render(request, 'events/edit.html', {
        'form': form,
        'event': event
    })


def list_events(request):
    """List all upcoming events with pagination."""
    # Track session for anonymous users
    SessionService.track_session(request, request.user if request.user.is_authenticated else None)

    events = EventQueryService.get_upcoming_events()

    # Filter by organization if specified
    organization_id = request.GET.get('organization')
    if organization_id:
        events = events.filter(organization_id=organization_id)

    paginator = Paginator(events, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'events/list.html', {
        'page_obj': page_obj,
        'events': page_obj.object_list
    })


def event_detail(request, pk):
    """Display event details and handle responses."""
    event = get_object_or_404(Event, pk=pk)

    # Track session
    SessionService.track_session(request, request.user if request.user.is_authenticated else None)

    user_response = None
    can_respond = False

    if request.user.is_authenticated:
        # Check if user is subscribed to this organization
        is_subscribed = Subscription.objects.filter(
            user=request.user,
            organization=event.organization
        ).exists()

        if is_subscribed:
            can_respond = True
            try:
                user_response = EventResponse.objects.get(event=event, user=request.user)
            except EventResponse.DoesNotExist:
                pass
    else:
        # Check anonymous subscription
        subscription_id = request.session.get(f'anonymous_subscription_{event.organization.pk}')
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
                pass

    if request.method == 'POST' and can_respond:
        form = EventResponseForm(request.POST)
        if form.is_valid():
            response_data = form.cleaned_data

            if request.user.is_authenticated:
                response, created = EventResponse.objects.update_or_create(
                    event=event,
                    user=request.user,
                    defaults={'response': response_data['response']}
                )
            else:
                subscription_id = request.session.get(f'anonymous_subscription_{event.organization.pk}')
                anonymous_subscription = AnonymousSubscription.objects.get(id=subscription_id)
                response, created = EventResponse.objects.update_or_create(
                    event=event,
                    anonymous_subscription=anonymous_subscription,
                    defaults={'response': response_data['response']}
                )

            action = "updated" if not created else "recorded"
            messages.success(request, f'Your response has been {action}!')
            return redirect('events:detail', pk=event.pk)
    else:
        form = EventResponseForm(instance=user_response)

    # Get response statistics
    stats = EventQueryService.get_event_response_stats(event)

    return render(request, 'events/detail.html', {
        'event': event,
        'form': form,
        'user_response': user_response,
        'can_respond': can_respond,
        'stats': stats,
        'can_manage': can_user_manage_event(request.user, event) if request.user.is_authenticated else False
    })


@login_required
@organization_required
def delete_event(request, pk):
    """Delete an event."""
    event = get_object_or_404(Event, pk=pk)

    if not can_user_manage_event(request.user, event):
        messages.error(request, 'You can only delete your own events.')
        return redirect('events:detail', pk=event.pk)

    if request.method == 'POST':
        event_title = event.title
        EventService.delete_event(event)
        messages.success(request, f'Event "{event_title}" deleted successfully!')
        return redirect('organizations:dashboard')

    return render(request, 'events/delete.html', {'event': event})


@login_required
def respond_to_event(request, pk):
    """Handle event response from authenticated users."""
    event = get_object_or_404(Event, pk=pk)

    # Check if user can respond (must be subscribed)
    if not Subscription.objects.filter(user=request.user, organization=event.organization).exists():
        messages.error(request, 'You must be subscribed to this organization to respond to events.')
        return redirect('events:detail', pk=event.pk)

    if request.method == 'POST':
        form = EventResponseForm(request.POST)
        if form.is_valid():
            response_data = form.cleaned_data
            response, created = EventResponse.objects.update_or_create(
                event=event,
                user=request.user,
                defaults={'response': response_data['response']}
            )

            action = "updated" if not created else "recorded"
            messages.success(request, f'Your response has been {action}!')

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': f'Response {action} successfully!'})

            return redirect('events:detail', pk=event.pk)
    else:
        try:
            existing_response = EventResponse.objects.get(event=event, user=request.user)
            form = EventResponseForm(instance=existing_response)
        except EventResponse.DoesNotExist:
            form = EventResponseForm()

    return render(request, 'events/respond.html', {
        'event': event,
        'form': form
    })


@login_required
@organization_required
def event_analytics(request, pk):
    """View analytics for a specific event."""
    event = get_object_or_404(Event, pk=pk)

    if not can_user_manage_event(request.user, event):
        messages.error(request, 'You can only view analytics for your own events.')
        return redirect('events:detail', pk=event.pk)

    stats = EventQueryService.get_event_response_stats(event)
    responses = EventResponse.objects.filter(event=event).select_related('user', 'anonymous_subscription')

    context = {
        'event': event,
        'stats': stats,
        'responses': responses,
    }

    return render(request, 'events/analytics.html', context)


# Redirect old availability URLs to accounts app
def set_availability(request, organization_id):
    """Redirect to accounts app for availability management."""
    return redirect('accounts:set_availability', organization_id=organization_id)


def set_anonymous_availability(request, organization_id, subscription_id):
    """Redirect to accounts app for anonymous availability management."""
    return redirect('accounts:set_anonymous_availability', organization_id=organization_id)


def anonymous_availability_access(request, organization_id, token):
    """Handle anonymous availability access via token."""
    organization = get_object_or_404(Organization, id=organization_id)

    try:
        anonymous_subscription = AnonymousSubscription.objects.get(
            organization=organization,
            verification_token=token
        )

        # Set session data for this user
        request.session[f'anonymous_subscription_{organization.pk}'] = anonymous_subscription.pk
        messages.success(request, f'Welcome back! You can now set your availability for {organization.name}.')
        return redirect('accounts:set_anonymous_availability', organization_id=organization.pk)

    except AnonymousSubscription.DoesNotExist:
        messages.error(request, 'Invalid access token.')
        return redirect('organizations:detail', pk=organization.pk)


def anonymous_availability_by_email(request, organization_id):
    """Handle anonymous availability access by email verification."""
    organization = get_object_or_404(Organization, id=organization_id)

    if request.method == 'POST':
        email = request.POST.get('email', '').lower().strip()

        try:
            anonymous_subscription = AnonymousSubscription.objects.get(
                organization=organization,
                email=email
            )

            # Set session data for this user
            request.session[f'anonymous_subscription_{organization.pk}'] = anonymous_subscription.pk
            messages.success(request, f'Welcome back! You can now set your availability for {organization.name}.')
            return redirect('accounts:set_anonymous_availability', organization_id=organization.pk)

        except AnonymousSubscription.DoesNotExist:
            messages.error(request, 'No subscription found with this email address.')

    return render(request, 'events/anonymous_email_access.html', {
        'organization': organization
    })


def subscribe_anonymous(request, organization_id):
    """Redirect to organizations app for anonymous subscription."""
    return redirect('organizations:anonymous_subscribe', pk=organization_id)

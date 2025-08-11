from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Event, UserAvailability, EventResponse
from .forms import EventForm, UserAvailabilityForm, EventResponseForm
from organizations.models import Organization, Subscription, AnonymousSubscription
from notifications.tasks import send_event_notifications
import json


@login_required
@login_required
def create_event(request):
    if request.user.user_type != 'organization':
        messages.error(request, 'Only organizations can create events.')
        return redirect('home')

    try:
        organization = request.user.organization
    except Organization.DoesNotExist:
        return redirect('organizations:create_profile')

    if request.method == 'POST':
        form = EventForm(request.POST)
        if form.is_valid():
            event = form.save(commit=False)
            event.organization = organization
            event.save()

            # Schedule notifications using the updated task
            notification_time = event.date_time - timezone.timedelta(hours=event.notification_hours_before)

            # Send immediate notification
            send_event_notifications.delay(event.id)

            # Also schedule reminder notification before the event
            send_event_notifications.apply_async(
                args=[event.id],
                eta=notification_time
            )

            messages.success(request,
                             f'Event created successfully! Notifications sent to {organization.subscription_set.count() + organization.anonymoussubscription_set.count()} subscribers.')
            return redirect('events:detail', pk=event.pk)
    else:
        form = EventForm()

    return render(request, 'events/create.html', {'form': form})

def event_detail(request, pk):
    event = get_object_or_404(Event, pk=pk)
    user_response = None
    can_respond = False

    if request.user.is_authenticated and request.user.user_type == 'user':
        # Check if user is subscribed to the organization
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

    response_counts = event.get_response_counts()

    context = {
        'event': event,
        'user_response': user_response,
        'can_respond': can_respond,
        'response_counts': response_counts,
    }

    return render(request, 'events/detail.html', context)


@login_required
def list_events(request):
    if request.user.user_type == 'organization':
        try:
            organization = request.user.organization
            events = Event.objects.filter(organization=organization).order_by('-date_time')
        except Organization.DoesNotExist:
            events = Event.objects.none()
    else:
        # Show events from subscribed organizations
        subscribed_orgs = Subscription.objects.filter(user=request.user).values_list('organization', flat=True)
        events = Event.objects.filter(organization__in=subscribed_orgs).order_by('-date_time')

    # Filter by upcoming/past
    filter_type = request.GET.get('filter', 'upcoming')
    if filter_type == 'upcoming':
        events = events.filter(date_time__gte=timezone.now())
    elif filter_type == 'past':
        events = events.filter(date_time__lt=timezone.now())

    paginator = Paginator(events, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'events/list.html', {
        'page_obj': page_obj,
        'filter_type': filter_type,
    })


@login_required
def edit_event(request, pk):
    event = get_object_or_404(Event, pk=pk)

    if request.user.user_type != 'organization' or event.organization.user != request.user:
        messages.error(request, 'You do not have permission to edit this event.')
        return redirect('events:detail', pk=pk)

    if request.method == 'POST':
        form = EventForm(request.POST, instance=event)
        if form.is_valid():
            form.save()
            messages.success(request, 'Event updated successfully!')
            return redirect('events:detail', pk=pk)
    else:
        form = EventForm(instance=event)

    return render(request, 'events/edit.html', {'form': form, 'event': event})


@login_required
def delete_event(request, pk):
    event = get_object_or_404(Event, pk=pk)

    if request.user.user_type != 'organization' or event.organization.user != request.user:
        messages.error(request, 'You do not have permission to delete this event.')
        return redirect('events:detail', pk=pk)

    if request.method == 'POST':
        event.delete()
        messages.success(request, 'Event deleted successfully!')
        return redirect('events:list')

    return render(request, 'events/delete.html', {'event': event})


@login_required
def set_availability(request, organization_id):
    if request.user.user_type != 'user':
        messages.error(request, 'Only regular users can set availability.')
        return redirect('home')

    organization = get_object_or_404(Organization, pk=organization_id)

    # Check if user is subscribed
    subscription = get_object_or_404(Subscription, user=request.user, organization=organization)

    # Get existing availability
    existing_availability = UserAvailability.objects.filter(
        user=request.user,
        organization=organization
    )

    if request.method == 'POST':
        form = UserAvailabilityForm(request.POST)
        if form.is_valid():
            availability_data = form.cleaned_data['availability_data']

            # Clear existing availability
            existing_availability.delete()

            # Create new availability entries
            for item in availability_data:
                UserAvailability.objects.create(
                    user=request.user,
                    organization=organization,
                    recurrence_type=item['recurrence_type'],
                    day_of_week=item.get('day_of_week'),
                    day_of_month=item.get('day_of_month'),
                    specific_date=item.get('specific_date'),
                    time_slots=item['time_slots'],
                    availability_type=item['availability_type']
                )

            # Update subscription notification preference
            notification_preference = request.POST.get('notification_preference', 'all')
            subscription.notification_preference = notification_preference
            subscription.save()

            messages.success(request, 'Availability updated successfully!')
            return redirect('organizations:detail', pk=organization_id)
    else:
        form = UserAvailabilityForm()

    # Convert existing availability to JSON for frontend
    availability_json = []
    for avail in existing_availability:
        availability_json.append({
            'recurrence_type': avail.recurrence_type,
            'day_of_week': avail.day_of_week,
            'day_of_month': avail.day_of_month,
            'specific_date': avail.specific_date.isoformat() if avail.specific_date else None,
            'time_slots': avail.time_slots,
            'availability_type': avail.availability_type
        })

    return render(request, 'events/set_availability.html', {
        'form': form,
        'organization': organization,
        'subscription': subscription,
        'existing_availability': json.dumps(availability_json),
    })


def set_anonymous_availability(request, organization_id, subscription_id):
    """Set availability for anonymous subscribers - NO LOGIN REQUIRED"""
    from organizations.models import AnonymousSubscription

    organization = get_object_or_404(Organization, pk=organization_id)
    anonymous_subscription = get_object_or_404(AnonymousSubscription, pk=subscription_id, organization=organization)

    # Get existing availability for this anonymous subscription
    existing_availability = UserAvailability.objects.filter(
        anonymous_subscription=anonymous_subscription,
        organization=organization
    )

    if request.method == 'POST':
        form = UserAvailabilityForm(request.POST)
        if form.is_valid():
            availability_data = form.cleaned_data['availability_data']

            # Clear existing availability
            existing_availability.delete()

            # Create new availability entries
            for item in availability_data:
                UserAvailability.objects.create(
                    anonymous_subscription=anonymous_subscription,
                    organization=organization,
                    recurrence_type=item['recurrence_type'],
                    day_of_week=item.get('day_of_week'),
                    day_of_month=item.get('day_of_month'),
                    specific_date=item.get('specific_date'),
                    time_slots=item['time_slots'],
                    availability_type=item['availability_type']
                )

            # Update notification preference
            notification_preference = request.POST.get('notification_preference', 'all')
            anonymous_subscription.notification_preference = notification_preference
            anonymous_subscription.save()

            messages.success(request, 'Availability updated successfully!')
            return redirect('organizations:detail', pk=organization_id)
    else:
        form = UserAvailabilityForm()

    # Convert existing availability to JSON for frontend
    availability_json = []
    for avail in existing_availability:
        availability_json.append({
            'recurrence_type': avail.recurrence_type,
            'day_of_week': avail.day_of_week,
            'day_of_month': avail.day_of_month,
            'specific_date': avail.specific_date.isoformat() if avail.specific_date else None,
            'time_slots': avail.time_slots,
            'availability_type': avail.availability_type
        })

    return render(request, 'events/set_anonymous_availability.html', {
        'form': form,
        'organization': organization,
        'anonymous_subscription': anonymous_subscription,
        'existing_availability': json.dumps(availability_json),
    })

@login_required
def respond_to_event(request, pk):
    event = get_object_or_404(Event, pk=pk)

    if request.user.user_type != 'user':
        messages.error(request, 'Only regular users can respond to events.')
        return redirect('events:detail', pk=pk)

    # Check if user is subscribed to the organization
    if not Subscription.objects.filter(user=request.user, organization=event.organization).exists():
        messages.error(request, 'You must be subscribed to this organization to respond to events.')
        return redirect('events:detail', pk=pk)

    response, created = EventResponse.objects.get_or_create(
        event=event,
        user=request.user,
        defaults={'response': 'maybe'}
    )

    if request.method == 'POST':
        form = EventResponseForm(request.POST, instance=response)
        if form.is_valid():
            form.save()
            messages.success(request, 'Response updated successfully!')
            return redirect('events:detail', pk=pk)
    else:
        form = EventResponseForm(instance=response)

    return render(request, 'events/respond.html', {
        'form': form,
        'event': event,
        'response': response,
    })


@login_required
def event_analytics(request, pk):
    event = get_object_or_404(Event, pk=pk)

    if request.user.user_type != 'organization' or event.organization.user != request.user:
        messages.error(request, 'You do not have permission to view analytics for this event.')
        return redirect('events:detail', pk=pk)

    responses = EventResponse.objects.filter(event=event).select_related('user')
    response_counts = event.get_response_counts()

    context = {
        'event': event,
        'responses': responses,
        'response_counts': response_counts,
        'total_responses': responses.count(),
    }

    return render(request, 'events/analytics.html', context)
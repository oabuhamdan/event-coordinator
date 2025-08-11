from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from events.models import Event
from .forms import OrganizationForm, AnonymousSubscriptionForm
from .models import Organization, Subscription, AnonymousSubscription


@login_required
def create_profile(request):
    if request.user.user_type != 'organization':
        messages.error(request, 'Only organizations can create organization profiles.')
        return redirect('home')

    try:
        organization = request.user.organization
        return redirect('organizations:dashboard')
    except Organization.DoesNotExist:
        pass

    if request.method == 'POST':
        form = OrganizationForm(request.POST, request.FILES)
        if form.is_valid():
            organization = form.save(commit=False)
            organization.user = request.user
            organization.save()
            messages.success(request, 'Organization profile created successfully!')
            return redirect('organizations:dashboard')
    else:
        form = OrganizationForm()

    return render(request, 'organizations/create_profile.html', {'form': form})


@login_required
def dashboard(request):
    if request.user.user_type != 'organization':
        messages.error(request, 'Access denied.')
        return redirect('home')

    try:
        organization = request.user.organization
    except Organization.DoesNotExist:
        return redirect('organizations:create_profile')

    # Get analytics data
    total_subscribers = Subscription.objects.filter(organization=organization).count()
    total_events = Event.objects.filter(organization=organization).count()
    upcoming_events = Event.objects.filter(
        organization=organization,
        date_time__gte=timezone.now()
    ).count()

    recent_events = Event.objects.filter(organization=organization).order_by('-created_at')[:5]

    context = {
        'organization': organization,
        'total_subscribers': total_subscribers,
        'total_events': total_events,
        'upcoming_events': upcoming_events,
        'recent_events': recent_events,
    }

    return render(request, 'organizations/dashboard.html', context)


@login_required
def edit_profile(request):
    if request.user.user_type != 'organization':
        messages.error(request, 'Access denied.')
        return redirect('home')

    try:
        organization = request.user.organization
    except Organization.DoesNotExist:
        return redirect('organizations:create_profile')

    if request.method == 'POST':
        form = OrganizationForm(request.POST, request.FILES, instance=organization)
        if form.is_valid():
            form.save()
            messages.success(request, 'Organization profile updated successfully!')
            return redirect('organizations:dashboard')
    else:
        form = OrganizationForm(instance=organization)

    return render(request, 'organizations/edit_profile.html', {'form': form, 'organization': organization})


def list_organizations(request):
    organizations = Organization.objects.all().order_by('name')
    return render(request, 'organizations/list.html', {'organizations': organizations})


def organization_detail(request, pk):
    organization = get_object_or_404(Organization, pk=pk)
    is_subscribed = False

    if request.user.is_authenticated and request.user.user_type == 'user':
        is_subscribed = Subscription.objects.filter(
            user=request.user,
            organization=organization
        ).exists()

    upcoming_events = Event.objects.filter(
        organization=organization,
        date_time__gte=timezone.now()
    ).order_by('date_time')[:5]

    context = {
        'organization': organization,
        'is_subscribed': is_subscribed,
        'upcoming_events': upcoming_events,
    }

    return render(request, 'organizations/detail.html', context)


@login_required
def subscribe(request, pk):
    if request.user.user_type != 'user':
        messages.error(request, 'Only regular users can subscribe to organizations.')
        return redirect('home')

    organization = get_object_or_404(Organization, pk=pk)
    subscription, created = Subscription.objects.get_or_create(
        user=request.user,
        organization=organization
    )

    if created:
        messages.success(request, f'Successfully subscribed to {organization.name}!')
        return redirect('events:set_availability', organization_id=pk)
    else:
        messages.info(request, f'You are already subscribed to {organization.name}.')
        return redirect('organizations:detail', pk=pk)


@login_required
def unsubscribe(request, pk):
    if request.user.user_type != 'user':
        messages.error(request, 'Access denied.')
        return redirect('home')

    organization = get_object_or_404(Organization, pk=pk)
    subscription = get_object_or_404(Subscription, user=request.user, organization=organization)
    subscription.delete()

    messages.success(request, f'Successfully unsubscribed from {organization.name}.')
    return redirect('organizations:detail', pk=pk)


@login_required
def subscribers(request):
    if request.user.user_type != 'organization':
        messages.error(request, 'Access denied.')
        return redirect('home')

    try:
        organization = request.user.organization
    except Organization.DoesNotExist:
        return redirect('organizations:create_profile')

    subscribers = Subscription.objects.filter(organization=organization).select_related('user')

    return render(request, 'organizations/subscribers.html', {
        'organization': organization,
        'subscribers': subscribers,
    })


@login_required
def availability_analytics(request):
    """Enhanced analytics dashboard with detailed subscriber breakdowns"""
    if request.user.user_type != 'organization':
        messages.error(request, 'Access denied.')
        return redirect('home')

    try:
        organization = request.user.organization
    except Organization.DoesNotExist:
        return redirect('organizations:create_profile')

    # Get date filter parameters
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    # Set default date range (next 30 days)
    today = timezone.now().date()
    start_date = today
    end_date = today + timedelta(days=30)

    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    # Get enhanced analytics data with detailed subscriber info
    analytics = organization.get_enhanced_availability_analytics(start_date, end_date)

    # Get subscriber details
    regular_subscribers = Subscription.objects.filter(organization=organization).select_related('user')
    anonymous_subscribers = AnonymousSubscription.objects.filter(organization=organization)

    context = {
        'organization': organization,
        'analytics': analytics,
        'total_regular_subscribers': regular_subscribers.count(),
        'total_anonymous_subscribers': anonymous_subscribers.count(),
        'start_date': start_date,
        'end_date': end_date,
    }

    return render(request, 'organizations/availability_analytics.html', context)


@login_required
def get_time_slot_details(request, organization_id):
    """AJAX endpoint to get detailed subscriber info for a specific time slot"""
    if request.user.user_type != 'organization':
        return JsonResponse({'error': 'Access denied'}, status=403)

    try:
        organization = request.user.organization
        if organization.id != organization_id:
            return JsonResponse({'error': 'Access denied'}, status=403)
    except Organization.DoesNotExist:
        return JsonResponse({'error': 'Organization not found'}, status=404)

    time_slot = request.GET.get('time_slot')
    if not time_slot:
        return JsonResponse({'error': 'Time slot required'}, status=400)

    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    # Parse dates
    today = timezone.now().date()
    start_date = today
    end_date = today + timedelta(days=30)

    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    # Get detailed subscriber info for this time slot
    details = organization.get_time_slot_subscriber_details(time_slot, start_date, end_date)

    return JsonResponse(details)


@login_required
def get_datetime_slot_details(request, organization_id):
    """AJAX endpoint to get detailed subscriber info for a specific datetime slot"""
    if request.user.user_type != 'organization':
        return JsonResponse({'error': 'Access denied'}, status=403)

    try:
        organization = request.user.organization
        if organization.id != organization_id:
            return JsonResponse({'error': 'Access denied'}, status=403)
    except Organization.DoesNotExist:
        return JsonResponse({'error': 'Organization not found'}, status=404)

    datetime_slot = request.GET.get('datetime_slot')
    if not datetime_slot:
        return JsonResponse({'error': 'DateTime slot required'}, status=400)

    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    # Parse dates
    today = timezone.now().date()
    start_date = today
    end_date = today + timedelta(days=30)

    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    # Get detailed subscriber info for this datetime slot
    details = organization.get_datetime_slot_subscriber_details(datetime_slot, start_date, end_date)

    return JsonResponse(details)


def anonymous_subscribe(request, pk):
    """Allow anonymous users to subscribe to an organization"""
    organization = get_object_or_404(Organization, pk=pk)

    if request.method == 'POST':
        form = AnonymousSubscriptionForm(request.POST)
        if form.is_valid():
            # Check if email already exists for this organization
            existing = AnonymousSubscription.objects.filter(
                email=form.cleaned_data['email'],
                organization=organization
            ).first()

            if existing:
                messages.warning(request,
                                 f'Email {form.cleaned_data["email"]} is already subscribed to {organization.name}.')
                return redirect('organizations:detail', pk=pk)

            subscription = form.save(commit=False)
            subscription.organization = organization
            subscription.save()

            messages.success(request,
                             f'Successfully subscribed to {organization.name}! You can now set your availability.')
            return redirect('events:set_anonymous_availability', organization_id=pk, subscription_id=subscription.id)
    else:
        form = AnonymousSubscriptionForm()

    return render(request, 'organizations/anonymous_subscribe.html', {
        'form': form,
        'organization': organization
    })

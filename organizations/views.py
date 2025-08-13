"""
Views for organization management, subscription handling, and analytics.
"""
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from accounts.models import UserAvailability  # This was missing
from accounts.services.session_service import SessionService
from accounts.utils import organization_required, regular_user_required
from events.models import Event
from .forms import OrganizationForm, SubscriptionForm, AnonymousSubscriptionForm
from .models import Organization, Subscription, AnonymousSubscription
from .services import (
    OrganizationService, OrganizationAnalyticsService, SubscriptionService,
    OrganizationQueryService, DateRangeService
)

User = get_user_model()


@login_required
@organization_required
def create_profile(request):
    """Create organization profile - only for organization users."""
    # Check if organization already exists
    existing_org = OrganizationService.get_organization_for_user(request.user)
    if existing_org:
        return redirect('organizations:dashboard')

    if request.method == 'POST':
        form = OrganizationForm(request.POST, request.FILES)
        if form.is_valid():
            organization_data = form.cleaned_data
            OrganizationService.create_organization(request.user, organization_data)
            messages.success(request, 'Organization profile created successfully!')
            return redirect('organizations:dashboard')
    else:
        form = OrganizationForm()

    return render(request, 'organizations/create_profile.html', {'form': form})


@login_required
@organization_required
def dashboard(request):
    """Organization dashboard with analytics."""
    organization = OrganizationService.get_organization_for_user(request.user)
    if not organization:
        return redirect('organizations:create_profile')

    stats = OrganizationAnalyticsService.get_dashboard_stats(organization)

    context = {
        'organization': organization,
        **stats,
    }

    return render(request, 'organizations/dashboard.html', context)


@login_required
@organization_required
def edit_profile(request):
    """Edit organization profile."""
    organization = OrganizationService.get_organization_for_user(request.user)
    if not organization:
        return redirect('organizations:create_profile')

    if request.method == 'POST':
        form = OrganizationForm(request.POST, request.FILES, instance=organization)
        if form.is_valid():
            form.save()
            messages.success(request, 'Organization profile updated successfully!')
            return redirect('organizations:dashboard')
    else:
        form = OrganizationForm(instance=organization)

    return render(request, 'organizations/edit_profile.html', {
        'form': form,
        'organization': organization
    })


def list_organizations(request):
    """List all organizations."""
    # Track session for anonymous users
    SessionService.track_session(request, request.user if request.user.is_authenticated else None)

    organizations = OrganizationQueryService.get_all_organizations()
    return render(request, 'organizations/list.html', {'organizations': organizations})


def organization_detail(request, pk):
    """Display organization details with unified subscription management."""
    organization = get_object_or_404(Organization, pk=pk)

    # Track session
    SessionService.track_session(request, request.user if request.user.is_authenticated else None)

    # Initialize context variables
    context = {
        'organization': organization,
        'is_subscribed': False,
        'subscription': None,
        'user_type': None,
        'subscriber_info': None,
    }

    # Check user type and subscription status
    if request.user.is_authenticated and request.user.is_regular_user:
        # Regular authenticated user
        context['user_type'] = 'registered'
        context['is_subscribed'] = SubscriptionService.is_user_subscribed(request.user, organization)

        if context['is_subscribed']:
            context['subscription'] = Subscription.objects.get(user=request.user, organization=organization)
            context['subscriber_info'] = {
                'name': request.user.username,
                'email': request.user.email,
                'phone_number': getattr(request.user, 'phone_number', ''),
                'whatsapp_number': getattr(request.user, 'whatsapp_number', ''),
                'notification_preference': context['subscription'].notification_preference,
                'user_type': 'registered'
            }
    else:
        # Anonymous user or organization user
        context['user_type'] = 'anonymous'
        subscription_id = request.session.get(f'anonymous_subscription_{organization.pk}')

        if subscription_id:
            try:
                anonymous_subscription = AnonymousSubscription.objects.get(id=subscription_id)
                context['is_subscribed'] = True
                context['subscription'] = anonymous_subscription
                context['subscriber_info'] = {
                    'name': anonymous_subscription.name,
                    'email': anonymous_subscription.email,
                    'phone_number': anonymous_subscription.phone_number,
                    'whatsapp_number': anonymous_subscription.whatsapp_number,
                    'notification_preference': anonymous_subscription.notification_preference,
                    'user_type': 'anonymous'
                }
            except AnonymousSubscription.DoesNotExist:
                # Clean up invalid session data
                del request.session[f'anonymous_subscription_{organization.pk}']

    # Get upcoming events for this organization
    upcoming_events = Event.objects.filter(
        organization=organization,
        date_time__gte=timezone.now()
    ).order_by('date_time')[:5]

    context['upcoming_events'] = upcoming_events

    return render(request, 'organizations/detail.html', context)


@login_required
@regular_user_required
def subscribe(request, pk):
    """Subscribe a registered user to an organization."""
    organization = get_object_or_404(Organization, pk=pk)

    if SubscriptionService.is_user_subscribed(request.user, organization):
        messages.info(request, f'You are already subscribed to {organization.name}.')
        return redirect('accounts:set_availability', organization_id=organization.pk)

    if request.method == 'POST':
        form = SubscriptionForm(request.POST)
        if form.is_valid():
            subscription_data = form.cleaned_data
            SubscriptionService.create_subscription(request.user, organization, subscription_data)
            messages.success(request, f'Successfully subscribed to {organization.name}!')
            return redirect('accounts:set_availability', organization_id=organization.pk)
    else:
        form = SubscriptionForm()

    return render(request, 'organizations/subscribe.html', {
        'form': form,
        'organization': organization
    })


@csrf_exempt
def anonymous_subscribe(request, pk):
    """Handle anonymous subscription to an organization."""
    organization = get_object_or_404(Organization, pk=pk)

    # Track session
    SessionService.track_session(request)

    if request.method == 'POST':
        # Check if already subscribed
        subscription_id = request.session.get(f'anonymous_subscription_{organization.pk}')
        if subscription_id:
            try:
                existing_subscription = AnonymousSubscription.objects.get(id=subscription_id)
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': True,
                        'already_subscribed': True,
                        'message': f'You are already subscribed to {organization.name}.',
                        'redirect_url': f'/accounts/availability/anonymous/set/{organization.pk}/'
                    })
                else:
                    messages.info(request, f'You are already subscribed to {organization.name}.')
                    return redirect('accounts:set_anonymous_availability', organization_id=organization.pk)
            except AnonymousSubscription.DoesNotExist:
                # Clean up invalid session data
                del request.session[f'anonymous_subscription_{organization.pk}']

        form = AnonymousSubscriptionForm(request.POST)
        if form.is_valid():
            subscription_data = form.cleaned_data

            # Check if email already exists for this organization
            existing = AnonymousSubscription.objects.filter(
                email=subscription_data['email'],
                organization=organization
            ).first()

            if existing:
                # Update session with existing subscription
                request.session[f'anonymous_subscription_{organization.pk}'] = existing.pk

                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': True,
                        'already_subscribed': True,
                        'message': f'Welcome back! You are already subscribed to {organization.name}.',
                        'redirect_url': f'/accounts/availability/anonymous/set/{organization.pk}/'
                    })
                else:
                    messages.success(request, f'Welcome back! You are already subscribed to {organization.name}.')
                    return redirect('accounts:set_anonymous_availability', organization_id=organization.pk)

            # Create new subscription
            subscription = SubscriptionService.create_anonymous_subscription(organization, subscription_data)
            request.session[f'anonymous_subscription_{organization.pk}'] = subscription.pk

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': f'Successfully subscribed to {organization.name}!',
                    'redirect_url': f'/accounts/availability/anonymous/set/{organization.pk}/'
                })
            else:
                messages.success(request, f'Successfully subscribed to {organization.name}!')
                return redirect('accounts:set_anonymous_availability', organization_id=organization.pk)
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'errors': form.errors
                })

    # GET request - show form
    form = AnonymousSubscriptionForm()
    return render(request, 'organizations/anonymous_subscribe.html', {
        'form': form,
        'organization': organization
    })


@login_required
@regular_user_required
def unsubscribe(request, pk):
    """Unsubscribe a user from an organization."""
    organization = get_object_or_404(Organization, pk=pk)

    if not SubscriptionService.is_user_subscribed(request.user, organization):
        messages.info(request, f'You are not subscribed to {organization.name}.')
        return redirect('organizations:detail', pk=organization.pk)

    if request.method == 'POST':
        success = SubscriptionService.delete_subscription(request.user, organization)
        if success:
            messages.success(request, f'Successfully unsubscribed from {organization.name}.')
        else:
            messages.error(request, f'Failed to unsubscribe from {organization.name}.')
        return redirect('organizations:detail', pk=organization.pk)

    return render(request, 'organizations/unsubscribe.html', {
        'organization': organization
    })


@login_required
@organization_required
def subscribers(request):
    """View organization subscribers without preloading availability."""
    organization = OrganizationService.get_organization_for_user(request.user)
    if not organization:
        return redirect('organizations:create_profile')

    # Get subscriber data without availability
    subscriber_data = SubscriptionService.get_organization_subscribers(organization)

    # Enhanced regular subscribers - just check if they have any availability
    regular_subscribers_data = []
    for subscription in subscriber_data['regular_subscribers']:
        has_availability = UserAvailability.objects.filter(
            user=subscription.user,
            organization=organization
        ).exists()

        availability_count = UserAvailability.objects.filter(
            user=subscription.user,
            organization=organization
        ).count() if has_availability else 0

        regular_subscribers_data.append({
            'subscription': subscription,
            'user': subscription.user,
            'has_availability': has_availability,
            'availability_count': availability_count
        })

    # Enhanced anonymous subscribers - just check if they have any availability
    anonymous_subscribers_data = []
    for subscription in subscriber_data['anonymous_subscribers']:
        has_availability = UserAvailability.objects.filter(
            anonymous_subscription=subscription,
            organization=organization
        ).exists()

        availability_count = UserAvailability.objects.filter(
            anonymous_subscription=subscription,
            organization=organization
        ).count() if has_availability else 0

        anonymous_subscribers_data.append({
            'subscription': subscription,
            'has_availability': has_availability,
            'availability_count': availability_count
        })

    # Sort both lists - users with availability first
    regular_subscribers_data.sort(key=lambda x: (not x['has_availability'], x['user'].username))
    anonymous_subscribers_data.sort(key=lambda x: (not x['has_availability'], x['subscription'].name))

    context = {
        'organization': organization,
        'regular_subscribers_data': regular_subscribers_data,
        'anonymous_subscribers_data': anonymous_subscribers_data,
        'total_subscribers': len(regular_subscribers_data) + len(anonymous_subscribers_data),
        'total_with_availability': sum(1 for sub in regular_subscribers_data if sub['has_availability']) +
                                   sum(1 for sub in anonymous_subscribers_data if sub['has_availability'])
    }

    return render(request, 'organizations/subscribers.html', context)


@login_required
@organization_required
def get_subscriber_availability(request, organization_id):
    """AJAX endpoint to get availability for a specific subscriber."""
    organization = get_object_or_404(Organization, id=organization_id)

    # Verify organization ownership
    if organization.user != request.user:
        return JsonResponse({'error': 'Permission denied'}, status=403)

    subscriber_type = request.GET.get('type')  # 'user' or 'anonymous'
    subscriber_id = request.GET.get('id')

    if not subscriber_type or not subscriber_id:
        return JsonResponse({'error': 'Missing parameters'}, status=400)

    try:
        # Get availability records
        if subscriber_type == 'user':
            user = get_object_or_404(User, id=subscriber_id)
            availability_records = UserAvailability.objects.filter(
                user=user,
                organization=organization
            ).order_by('recurrence_type', 'day_of_week', 'day_of_month', 'specific_date')

            subscriber_name = user.username
            subscriber_email = user.email

        elif subscriber_type == 'anonymous':
            anonymous_sub = get_object_or_404(AnonymousSubscription, id=subscriber_id)
            availability_records = UserAvailability.objects.filter(
                anonymous_subscription=anonymous_sub,
                organization=organization
            ).order_by('recurrence_type', 'day_of_week', 'day_of_month', 'specific_date')

            subscriber_name = anonymous_sub.name or "Anonymous User"
            subscriber_email = anonymous_sub.email

        else:
            return JsonResponse({'error': 'Invalid subscriber type'}, status=400)

        # Format availability data
        availability_data = []
        for availability in availability_records:
            # Get display name for recurrence
            if availability.recurrence_type == 'weekly':
                day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                recurrence_display = day_names[availability.day_of_week]
                recurrence_icon = 'fas fa-calendar-week'
            elif availability.recurrence_type == 'monthly':
                recurrence_display = f"Day {availability.day_of_month} of month"
                recurrence_icon = 'fas fa-calendar-day'
            elif availability.recurrence_type == 'specific_date':
                recurrence_display = availability.specific_date.strftime('%b %d, %Y')
                recurrence_icon = 'fas fa-calendar'
            else:
                recurrence_display = "Unknown"
                recurrence_icon = 'fas fa-question'

            availability_data.append({
                'id': availability.id,
                'recurrence_type': availability.recurrence_type,
                'recurrence_display': recurrence_display,
                'recurrence_icon': recurrence_icon,
                'time_slots': availability.time_slots,
                'availability_type': availability.availability_type,
                'availability_type_display': availability.get_availability_type_display(),
                'created_at': availability.created_at.strftime('%Y-%m-%d %H:%M')
            })

        return JsonResponse({
            'success': True,
            'subscriber_name': subscriber_name,
            'subscriber_email': subscriber_email,
            'subscriber_type': subscriber_type,
            'availability_data': availability_data,
            'total_records': len(availability_data)
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@organization_required
def availability_analytics(request):
    """View availability analytics for organization."""
    organization = OrganizationService.get_organization_for_user(request.user)
    if not organization:
        return redirect('organizations:create_profile')

    # Get date range from request
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    start_date, end_date = DateRangeService.parse_date_range(start_date_str, end_date_str)

    analytics_data = organization.get_enhanced_availability_analytics(start_date, end_date)

    # Get additional stats for the template
    subscriber_data = SubscriptionService.get_organization_subscribers(organization)
    total_regular_subscribers = subscriber_data['regular_subscribers'].count()
    total_anonymous_subscribers = subscriber_data['anonymous_subscribers'].count()

    # Process analytics data for template
    analytics = analytics_data

    # Get top 6 datetime slots - FIXED: Sort by total_count instead of score
    top_datetime_slots = []
    if analytics.get('datetime_slot_scores'):
        sorted_slots = sorted(
            analytics['datetime_slot_scores'].items(),
            key=lambda x: x[1]['total_count'],  # Changed from 'score' to 'total_count'
            reverse=True
        )[:6]
        top_datetime_slots = sorted_slots

    # Calculate days in range
    days_in_range = (end_date - start_date).days + 1

    # Only include weekly_summary
    weekly_summary = analytics.get('weekly_summary', {})

    context = {
        'organization': organization,
        'analytics': {
            **analytics,
            'top_datetime_slots': top_datetime_slots,
            'days_in_range': days_in_range,
            'weekly_summary': weekly_summary,
        },
        'start_date': start_date,
        'end_date': end_date,
        'total_regular_subscribers': total_regular_subscribers,
        'total_anonymous_subscribers': total_anonymous_subscribers,
    }

    return render(request, 'organizations/availability_analytics.html', context)


@login_required
@organization_required
def get_datetime_slot_details(request, organization_id):
    """Get datetime slot details via AJAX."""
    organization = get_object_or_404(Organization, id=organization_id)

    # Verify organization ownership
    if organization.user != request.user:
        return JsonResponse({'error': 'Permission denied'}, status=403)

    datetime_slot = request.GET.get('datetime_slot')
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    if not datetime_slot:
        return JsonResponse({'error': 'datetime_slot parameter is required'}, status=400)

    start_date, end_date = DateRangeService.parse_date_range(start_date_str, end_date_str)

    try:
        details = organization.get_datetime_slot_subscriber_details(datetime_slot, start_date, end_date)
        return JsonResponse(details)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

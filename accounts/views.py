"""
Views for user accounts and availability management.
"""
from datetime import datetime

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import login
from django.contrib import messages
from django.http import JsonResponse
import json

from .forms import (
    AvailabilityForm, UserRegistrationForm,
    OrganizationRegistrationForm, ProfileUpdateForm
)
from .services.availability_service import AvailabilityService
from .services.session_service import SessionService
from .utils import regular_user_required
from organizations.models import Organization, AnonymousSubscription
from organizations.services import SubscriptionService


def register_user(request):
    """Register a new regular user."""
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Welcome {user.username}! Your account has been created.')
            return redirect('organizations:list')
    else:
        form = UserRegistrationForm()

    return render(request, 'accounts/register.html', {
        'form': form,
        'user_type': 'user',
        'title': 'Register as User'
    })


def register_organization(request):
    """Register a new organization user."""
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = OrganizationRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Welcome {user.username}! Please create your organization profile.')
            return redirect('organizations:create_profile')
    else:
        form = OrganizationRegistrationForm()

    return render(request, 'accounts/register.html', {
        'form': form,
        'user_type': 'organization',
        'title': 'Register as Organization'
    })


@login_required
def profile(request):
    """User profile management."""
    if request.method == 'POST':
        if 'change_password' in request.POST:
            return _handle_password_change(request)
        else:
            return _handle_profile_update(request)

    profile_form = ProfileUpdateForm(instance=request.user)
    password_form = PasswordChangeForm(request.user)

    return render(request, 'accounts/profile.html', {
        'profile_form': profile_form,
        'password_form': password_form
    })


def _handle_password_change(request):
    """Handle password change form submission."""
    password_form = PasswordChangeForm(request.user, request.POST)
    if password_form.is_valid():
        password_form.save()
        messages.success(request, 'Your password has been changed successfully!')
        return redirect('accounts:profile')
    else:
        profile_form = ProfileUpdateForm(instance=request.user)
        return render(request, 'accounts/profile.html', {
            'profile_form': profile_form,
            'password_form': password_form
        })


def _handle_profile_update(request):
    """Handle profile update form submission."""
    profile_form = ProfileUpdateForm(request.POST, instance=request.user)
    if profile_form.is_valid():
        profile_form.save()
        messages.success(request, 'Your profile has been updated successfully!')
        return redirect('accounts:profile')
    else:
        password_form = PasswordChangeForm(request.user)
        return render(request, 'accounts/profile.html', {
            'profile_form': profile_form,
            'password_form': password_form
        })


@login_required
@regular_user_required
def set_availability(request, username):
    """Set availability for a registered user."""
    organization = get_object_or_404(Organization, user__username=username)

    # Check subscription
    if not SubscriptionService.is_user_subscribed(request.user, organization):
        messages.error(request, 'You must be subscribed to set availability.')
        return redirect('organizations:detail', username=organization.user.username)

    # Track session
    SessionService.track_session(request, request.user)

    if request.method == 'POST':
        return _handle_availability_update(request, organization, user=request.user)

    return _render_availability_form(request, organization, user=request.user)


def set_anonymous_availability(request, username):
    """Set availability for an anonymous user."""
    organization = get_object_or_404(Organization, user__username=username)

    # Get anonymous subscription
    anonymous_subscription = _get_anonymous_subscription(request, organization)
    if not anonymous_subscription:
        messages.error(request, 'No subscription found. Please subscribe first.')
        return redirect('organizations:detail', username=organization.user.username)

    # Track session
    SessionService.track_session(request)

    if request.method == 'POST':
        return _handle_availability_update(
            request, organization,
            anonymous_subscription=anonymous_subscription
        )

    return _render_availability_form(
        request, organization,
        anonymous_subscription=anonymous_subscription
    )


def _handle_availability_update(request, organization, user=None, anonymous_subscription=None):
    """Handle availability form submission."""
    form = AvailabilityForm(request.POST)

    if form.is_valid():
        try:
            created_records = form.save(
                user=user,
                anonymous_subscription=anonymous_subscription,
                organization=organization
            )

            if len(created_records) == 0:
                success_msg = 'Your availability has been cleared successfully!'
            else:
                success_msg = f'Your availability has been updated! Saved {len(created_records)} availability records.'

            messages.success(request, success_msg)

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': success_msg})

            # Stay on the same page instead of redirecting
            return _render_availability_form(
                request, organization, user=user,
                anonymous_subscription=anonymous_subscription
            )

        except Exception as e:
            error_msg = f'Error updating availability: {str(e)}'
            messages.error(request, error_msg)

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': str(e)})

    # Form has errors, re-render
    return _render_availability_form(
        request, organization, user=user,
        anonymous_subscription=anonymous_subscription, form=form
    )

def _render_availability_form(request, organization, user=None, anonymous_subscription=None, form=None):
    """Render availability form with existing data."""
    if not form:
        form = AvailabilityForm()

    # Get existing availability
    existing_availability = AvailabilityService.get_user_availability(
        user=user,
        anonymous_subscription=anonymous_subscription,
        organization=organization
    )

    availability_data = AvailabilityService.serialize_availability(existing_availability)

    # Day choices for template
    day_choices = [
        (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'), (3, 'Thursday'),
        (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday')
    ]

    context = {
        'form': form,
        'organization': organization,
        'existing_availability': json.dumps(availability_data),
        'user_type': 'registered' if user else 'anonymous',
        'user': user or anonymous_subscription,
        'day_choices': day_choices,
        'today': datetime.now().date(),  # Add today's date for min date
    }

    if anonymous_subscription:
        context['anonymous_subscription'] = anonymous_subscription

    return render(request, 'accounts/availability_form.html', context)

def anonymous_profile(request, username):
    """Anonymous user profile management."""
    organization = get_object_or_404(Organization, user__username=username)

    anonymous_subscription = _get_anonymous_subscription(request, organization)
    if not anonymous_subscription:
        messages.error(request, 'No subscription found.')
        return redirect('organizations:detail', username=organization.user.username)

    if request.method == 'POST':
        if 'unsubscribe' in request.POST:
            return _handle_anonymous_unsubscribe(request, organization, anonymous_subscription)
        else:
            return _handle_anonymous_profile_update(request, organization, anonymous_subscription)

    return render(request, 'accounts/anonymous_profile.html', {
        'organization': organization,
        'anonymous_subscription': anonymous_subscription,
    })


def _get_anonymous_subscription(request, organization):
    """Get anonymous subscription from session."""
    subscription_id = request.session.get(f'anonymous_subscription_{organization.pk}')
    if not subscription_id:
        return None

    try:
        return AnonymousSubscription.objects.get(id=subscription_id)
    except AnonymousSubscription.DoesNotExist:
        # Clean up invalid session data
        del request.session[f'anonymous_subscription_{organization.pk}']
        return None


def _handle_anonymous_unsubscribe(request, organization, anonymous_subscription):
    """Handle anonymous user unsubscription."""
    anonymous_subscription.delete()
    del request.session[f'anonymous_subscription_{organization.pk}']
    messages.success(request, f'You have been unsubscribed from {organization.name}.')
    return redirect('organizations:detail', username=organization.user.username)


def _handle_anonymous_profile_update(request, organization, anonymous_subscription):
    """Handle anonymous profile update."""
    anonymous_subscription.name = request.POST.get('name', anonymous_subscription.name)
    anonymous_subscription.email = request.POST.get('email', anonymous_subscription.email)
    anonymous_subscription.phone_number = request.POST.get('phone_number', anonymous_subscription.phone_number)
    anonymous_subscription.whatsapp_number = request.POST.get('whatsapp_number', anonymous_subscription.whatsapp_number)
    anonymous_subscription.notification_preference = request.POST.get('notification_preference',
                                                                      anonymous_subscription.notification_preference)
    anonymous_subscription.save()

    messages.success(request, 'Your profile has been updated successfully!')
    return redirect('accounts:anonymous_profile', username=organization.user.username)


@login_required
@regular_user_required
def get_availability(request, username):
    """Get user's availability for an organization (API endpoint)."""
    organization = get_object_or_404(Organization, user__username=username)

    availability = AvailabilityService.get_user_availability(
        user=request.user, organization=organization
    )

    availability_data = AvailabilityService.serialize_availability(availability)
    return JsonResponse({'availability': availability_data})
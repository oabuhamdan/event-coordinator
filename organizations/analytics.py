"""
Analytics utilities for organizations.
This module contains helper functions for analyzing availability data.
"""
from datetime import datetime, time
from collections import defaultdict


def time_to_minutes(t):
    """Convert time to minutes since midnight for easier calculations"""
    return t.hour * 60 + t.minute


def minutes_to_time(minutes):
    """Convert minutes since midnight back to time"""
    return time(hour=minutes // 60, minute=minutes % 60)


def collect_subscriber_slots(availabilities, date_range, days_of_week):
    """
    Collect all subscriber availability slots
    Returns a list of slots with subscriber info, date, and time details
    """
    subscriber_slots = []

    for availability in availabilities:
        # Get subscriber info
        if availability.user:
            subscriber_info = {
                'id': f"user_{availability.user.id}",
                'name': availability.user.username,
                'email': availability.user.email,
                'type': 'registered',
                'availability_type': availability.availability_type
            }
        elif availability.anonymous_subscription:
            subscriber_info = {
                'id': f"anon_{availability.anonymous_subscription.id}",
                'name': availability.anonymous_subscription.name,
                'email': availability.anonymous_subscription.email,
                'type': 'anonymous',
                'availability_type': availability.availability_type
            }
        else:
            continue

        # Find applicable dates
        applicable_dates = []
        for check_date in date_range:
            applies = False

            if availability.recurrence_type == 'weekly':
                if availability.day_of_week == check_date.weekday():
                    applies = True
            elif availability.recurrence_type == 'monthly':
                if availability.day_of_month == check_date.day:
                    applies = True
            elif availability.recurrence_type == 'specific_date':
                if availability.specific_date == check_date:
                    applies = True

            if applies:
                applicable_dates.append(check_date)

        # Add slots for each applicable date
        for date in applicable_dates:
            for time_slot in availability.time_slots:
                start_time = datetime.strptime(time_slot['start'], '%H:%M').time()
                end_time = datetime.strptime(time_slot['end'], '%H:%M').time()

                subscriber_slots.append({
                    'subscriber': subscriber_info,
                    'date': date,
                    'start_time': start_time,
                    'end_time': end_time,
                    'day_name': days_of_week[date.weekday()],
                    'recurrence_type': availability.recurrence_type
                })

    return subscriber_slots


def find_time_boundaries(subscriber_slots):
    """
    Find all time boundaries for each date
    Returns a dictionary mapping dates to sets of time boundaries (in minutes)
    """
    time_boundaries_by_date = defaultdict(set)

    for slot in subscriber_slots:
        date = slot['date']
        start_minutes = time_to_minutes(slot['start_time'])
        end_minutes = time_to_minutes(slot['end_time'])

        time_boundaries_by_date[date].add(start_minutes)
        time_boundaries_by_date[date].add(end_minutes)

    return time_boundaries_by_date


def analyze_time_periods(subscriber_slots, time_boundaries_by_date):
    """
    Analyze all possible time periods and find subscribers for each
    Returns datetime_slot_details (removed time_slot_aggregation)
    """
    datetime_slot_details = defaultdict(lambda: {'sure': [], 'maybe': []})

    for date, boundaries in time_boundaries_by_date.items():
        # Sort boundaries and create periods between each pair
        sorted_boundaries = sorted(boundaries)

        for i in range(len(sorted_boundaries) - 1):
            period_start_minutes = sorted_boundaries[i]
            period_end_minutes = sorted_boundaries[i + 1]

            period_start_time = minutes_to_time(period_start_minutes)
            period_end_time = minutes_to_time(period_end_minutes)

            # Find all subscribers available during this period
            period_subscribers = {'sure': [], 'maybe': []}
            subscriber_ids_seen = set()  # Prevent duplicates

            for slot in subscriber_slots:
                if slot['date'] != date:
                    continue

                slot_start_minutes = time_to_minutes(slot['start_time'])
                slot_end_minutes = time_to_minutes(slot['end_time'])

                # Check if subscriber's slot covers this period
                if (slot_start_minutes <= period_start_minutes and
                        slot_end_minutes >= period_end_minutes):

                    subscriber_id = slot['subscriber']['id']
                    if subscriber_id not in subscriber_ids_seen:
                        subscriber_ids_seen.add(subscriber_id)

                        avail_type = slot['subscriber']['availability_type']

                        subscriber_detail = {
                            **slot['subscriber'],
                            'time_slot': f"{period_start_time.strftime('%H:%M')}-{period_end_time.strftime('%H:%M')}",
                            'date': date.strftime('%Y-%m-%d'),
                            'day_name': slot['day_name'],
                            'recurrence_type': slot['recurrence_type'],
                        }

                        period_subscribers[avail_type].append(subscriber_detail)

            # Only store periods that have subscribers
            if period_subscribers['sure'] or period_subscribers['maybe']:
                time_key = f"{period_start_time.strftime('%H:%M')}-{period_end_time.strftime('%H:%M')}"
                datetime_key = f"{date.strftime('%Y-%m-%d')} {time_key}"

                datetime_slot_details[datetime_key] = period_subscribers

    return datetime_slot_details


def calculate_slot_scores(datetime_slot_details, days_of_week):
    """
    Calculate scores for ranking datetime slots only
    Returns datetime_slot_scores (removed time_slot_scores)
    """
    datetime_slot_scores = {}
    for datetime_slot, data in datetime_slot_details.items():
        sure_count = len(data['sure'])
        maybe_count = len(data['maybe'])

        if sure_count > 0 or maybe_count > 0:
            parts = datetime_slot.split(' ')
            date_part = parts[0]
            time_part = parts[1]

            date_obj = datetime.strptime(date_part, '%Y-%m-%d').date()
            day_name = days_of_week[date_obj.weekday()]
            formatted_date = date_obj.strftime('%b %d, %Y')

            datetime_slot_scores[datetime_slot] = {
                'sure_count': sure_count,
                'maybe_count': maybe_count,
                'total_count': sure_count + maybe_count,
                'date': date_part,
                'time': time_part,
                'day_name': day_name,
                'formatted_date': formatted_date,
                'display': f"{day_name}, {formatted_date} at {time_part}"
            }

    return datetime_slot_scores


def prepare_weekly_summary(subscriber_slots):
    """
    Prepare weekly summary only (removed monthly summary)
    Returns weekly_summary
    """
    days_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

    # Track unique subscribers per day to avoid duplicates
    weekly_details = defaultdict(lambda: {'subscribers': []})
    weekly_subscriber_ids = defaultdict(set)

    for slot in subscriber_slots:
        subscriber_id = slot['subscriber']['id']
        day_name = slot['day_name']

        # Weekly summary only
        if (slot['recurrence_type'] == 'weekly' and
                subscriber_id not in weekly_subscriber_ids[day_name]):
            weekly_subscriber_ids[day_name].add(subscriber_id)
            subscriber_detail = {
                **slot['subscriber'],
                'time_slot': f"{slot['start_time'].strftime('%H:%M')}-{slot['end_time'].strftime('%H:%M')}",
                'date': slot['date'].strftime('%Y-%m-%d'),
                'day_name': day_name,
                'recurrence_type': slot['recurrence_type'],
            }
            weekly_details[day_name]['subscribers'].append(subscriber_detail)

    # Prepare final weekly summary
    weekly_summary = {}
    for day in days_of_week:
        subscribers = weekly_details[day]['subscribers']
        weekly_summary[day] = {
            'subscriber_count': len(subscribers),
            'sure_count': len([s for s in subscribers if s['availability_type'] == 'sure']),
            'maybe_count': len([s for s in subscribers if s['availability_type'] == 'maybe']),
            'subscribers': subscribers
        }

    return weekly_summary


def get_availability_analytics(organization, start_date=None, end_date=None):
    """
    Get enhanced availability analytics for an organization
    This is the main function called by the Organization model
    """
    from accounts.models import UserAvailability
    from datetime import timedelta, date
    from django.utils import timezone

    # Set default date range if not provided
    if not start_date:
        start_date = timezone.now().date()
    if not end_date:
        end_date = start_date + timedelta(days=30)

    # Ensure start_date and end_date are date objects
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

    # Generate date range
    date_range = []
    current_date = start_date
    while current_date <= end_date:
        date_range.append(current_date)
        current_date += timedelta(days=1)

    # Get all availability records for this organization
    availabilities = UserAvailability.objects.filter(organization=organization)

    if not availabilities.exists():
        return {
            'datetime_slot_details': {},
            'datetime_slot_scores': {},
            'weekly_summary': {},
            'total_subscribers': 0,
            'date_range': f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
            'start_date': start_date,
            'end_date': end_date,
        }

    days_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

    # Collect all subscriber slots
    subscriber_slots = collect_subscriber_slots(availabilities, date_range, days_of_week)

    if not subscriber_slots:
        return {
            'datetime_slot_details': {},
            'datetime_slot_scores': {},
            'weekly_summary': {},
            'total_subscribers': availabilities.count(),
            'date_range': f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
            'start_date': start_date,
            'end_date': end_date,
        }

    # Find time boundaries for each date
    time_boundaries_by_date = find_time_boundaries(subscriber_slots)

    # Analyze time periods and find overlaps
    datetime_slot_details = analyze_time_periods(subscriber_slots, time_boundaries_by_date)

    # Calculate scores for ranking
    datetime_slot_scores = calculate_slot_scores(datetime_slot_details, days_of_week)

    # Prepare weekly summary only
    weekly_summary = prepare_weekly_summary(subscriber_slots)

    return {
        'datetime_slot_details': datetime_slot_details,
        'datetime_slot_scores': datetime_slot_scores,
        'weekly_summary': weekly_summary,
        'total_subscribers': len(set(slot['subscriber']['id'] for slot in subscriber_slots)),
        'date_range': f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
        'start_date': start_date,
        'end_date': end_date,
    }


def get_datetime_slot_subscriber_details(organization, datetime_slot, start_date, end_date):
    """
    Get detailed subscriber information for a specific datetime slot
    """
    from accounts.models import UserAvailability
    from datetime import timedelta
    from django.utils import timezone

    # Parse datetime_slot (format: "YYYY-MM-DD HH:MM-HH:MM")
    try:
        date_part, time_part = datetime_slot.split(' ')
        slot_date = datetime.strptime(date_part, '%Y-%m-%d').date()
        start_time_str, end_time_str = time_part.split('-')
        slot_start = datetime.strptime(start_time_str, '%H:%M').time()
        slot_end = datetime.strptime(end_time_str, '%H:%M').time()
    except (ValueError, AttributeError):
        return {
            'datetime_slot': datetime_slot,
            'subscribers': {'sure': [], 'maybe': []},
            'error': 'Invalid datetime slot format'
        }

    # Get availability data for the date range
    analytics_data = get_availability_analytics(organization, start_date, end_date)

    # Find subscribers for this specific datetime slot
    slot_details = analytics_data['datetime_slot_details'].get(datetime_slot, {'sure': [], 'maybe': []})

    return {
        'datetime_slot': datetime_slot,
        'subscribers': slot_details,
        'total_sure': len(slot_details.get('sure', [])),
        'total_maybe': len(slot_details.get('maybe', [])),
        'total': len(slot_details.get('sure', [])) + len(slot_details.get('maybe', []))
    }
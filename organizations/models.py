from django.db import models
from django.conf import settings
from collections import defaultdict
from datetime import datetime, time
from django.db import models
from django.conf import settings
from collections import defaultdict
from datetime import datetime, time, timedelta
from django.utils import timezone


class Organization(models.Model):
    NOTIFICATION_TYPES = [
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('whatsapp', 'WhatsApp'),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    website = models.URLField(blank=True)
    logo = models.ImageField(upload_to='organization_logos/', blank=True, null=True)

    # API Configurations
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='email')

    # Email API settings
    smtp_host = models.CharField(max_length=200, blank=True)
    smtp_port = models.IntegerField(blank=True, null=True)
    smtp_username = models.CharField(max_length=200, blank=True)
    smtp_password = models.CharField(max_length=200, blank=True)

    # SMS/WhatsApp API settings (Twilio)
    twilio_account_sid = models.CharField(max_length=200, blank=True)
    twilio_auth_token = models.CharField(max_length=200, blank=True)
    twilio_phone_number = models.CharField(max_length=20, blank=True)
    twilio_whatsapp_number = models.CharField(max_length=20, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def get_enhanced_availability_analytics(self, start_date=None, end_date=None):
        """Get enhanced analytics with simplified overlap detection"""
        from events.models import UserAvailability

        if not start_date:
            start_date = timezone.now().date()
        if not end_date:
            end_date = start_date + timedelta(days=30)

        # Get all availability data for this organization
        availabilities = UserAvailability.objects.filter(organization=self)

        days_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

        # Generate all dates in the range
        date_range = []
        current_date = start_date
        while current_date <= end_date:
            date_range.append(current_date)
            current_date += timedelta(days=1)

        # Step 1: Collect all subscriber availability slots
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

        # Step 2: Find all unique time periods (both original and overlapping)
        def time_to_minutes(t):
            """Convert time to minutes since midnight for easier calculations"""
            return t.hour * 60 + t.minute

        def minutes_to_time(minutes):
            """Convert minutes since midnight back to time"""
            return time(hour=minutes // 60, minute=minutes % 60)

        # Collect all time boundaries for each date
        time_boundaries_by_date = defaultdict(set)

        for slot in subscriber_slots:
            date = slot['date']
            start_minutes = time_to_minutes(slot['start_time'])
            end_minutes = time_to_minutes(slot['end_time'])

            time_boundaries_by_date[date].add(start_minutes)
            time_boundaries_by_date[date].add(end_minutes)

        # Step 3: Create all possible time periods and find subscribers for each
        datetime_slot_details = defaultdict(lambda: {'sure': [], 'maybe': []})
        time_slot_aggregation = defaultdict(lambda: {'sure': set(), 'maybe': set()})

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

                            # Aggregate for time slot summary (across all dates)
                            time_key = f"{period_start_time.strftime('%H:%M')}-{period_end_time.strftime('%H:%M')}"
                            time_slot_aggregation[time_key][avail_type].add(subscriber_id)

                # Only store periods that have subscribers
                if period_subscribers['sure'] or period_subscribers['maybe']:
                    time_key = f"{period_start_time.strftime('%H:%M')}-{period_end_time.strftime('%H:%M')}"
                    datetime_key = f"{date.strftime('%Y-%m-%d')} {time_key}"

                    datetime_slot_details[datetime_key] = period_subscribers

        # Step 4: Calculate scores for ranking
        datetime_slot_scores = {}
        for datetime_slot, data in datetime_slot_details.items():
            sure_count = len(data['sure'])
            maybe_count = len(data['maybe'])
            score = sure_count * 2 + maybe_count

            if score > 0:
                parts = datetime_slot.split(' ')
                date_part = parts[0]
                time_part = parts[1]

                date_obj = datetime.strptime(date_part, '%Y-%m-%d').date()
                day_name = days_of_week[date_obj.weekday()]
                formatted_date = date_obj.strftime('%b %d, %Y')

                datetime_slot_scores[datetime_slot] = {
                    'score': score,
                    'sure_count': sure_count,
                    'maybe_count': maybe_count,
                    'total_count': sure_count + maybe_count,
                    'date': date_part,
                    'time': time_part,
                    'day_name': day_name,
                    'formatted_date': formatted_date,
                    'display': f"{day_name}, {formatted_date} at {time_part}"
                }

        # Calculate time slot scores (aggregated across dates)
        time_slot_scores = {}
        for time_slot, data in time_slot_aggregation.items():
            sure_count = len(data['sure'])
            maybe_count = len(data['maybe'])
            score = sure_count * 2 + maybe_count

            if score > 0:
                time_slot_scores[time_slot] = {
                    'score': score,
                    'sure_count': sure_count,
                    'maybe_count': maybe_count,
                    'total_count': sure_count + maybe_count
                }

        # Get top results
        top_datetime_slots = sorted(
            datetime_slot_scores.items(),
            key=lambda x: x[1]['score'],
            reverse=True
        )[:6]

        top_time_slots = sorted(
            time_slot_scores.items(),
            key=lambda x: x[1]['score'],
            reverse=True
        )[:6]

        # Step 5: Prepare weekly and monthly summaries
        weekly_details = defaultdict(lambda: {'subscribers': []})
        monthly_details = defaultdict(lambda: {'subscribers': []})

        # Track unique subscribers per day/month to avoid duplicates
        weekly_subscriber_ids = defaultdict(set)
        monthly_subscriber_ids = defaultdict(set)

        for slot in subscriber_slots:
            subscriber_id = slot['subscriber']['id']
            day_name = slot['day_name']
            day_of_month = slot['date'].day

            # Weekly summary
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

            # Monthly summary
            if (slot['recurrence_type'] == 'monthly' and
                    subscriber_id not in monthly_subscriber_ids[day_of_month]):
                monthly_subscriber_ids[day_of_month].add(subscriber_id)
                subscriber_detail = {
                    **slot['subscriber'],
                    'time_slot': f"{slot['start_time'].strftime('%H:%M')}-{slot['end_time'].strftime('%H:%M')}",
                    'date': slot['date'].strftime('%Y-%m-%d'),
                    'day_name': day_name,
                    'recurrence_type': slot['recurrence_type'],
                }
                monthly_details[day_of_month]['subscribers'].append(subscriber_detail)

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

        # Prepare final monthly summary
        monthly_summary = {}
        for day in range(1, 32):
            subscribers = monthly_details[day]['subscribers']
            monthly_summary[day] = {
                'subscriber_count': len(subscribers),
                'sure_count': len([s for s in subscribers if s['availability_type'] == 'sure']),
                'maybe_count': len([s for s in subscribers if s['availability_type'] == 'maybe']),
                'subscribers': subscribers
            }

        return {
            'top_datetime_slots': top_datetime_slots,
            'top_time_slots': top_time_slots,
            'datetime_slot_details': dict(datetime_slot_details),
            'time_slot_details': {k: {'sure': list(v['sure']), 'maybe': list(v['maybe'])}
                                  for k, v in time_slot_aggregation.items()},
            'weekly_summary': weekly_summary,
            'monthly_summary': monthly_summary,
            'total_subscribers': self.subscription_set.count() + self.anonymoussubscription_set.count(),
            'date_range': f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
            'days_in_range': len(date_range)
        }

    def get_datetime_slot_subscriber_details(self, datetime_slot, start_date, end_date):
        """Get detailed subscriber info for a specific datetime slot"""
        analytics = self.get_enhanced_availability_analytics(start_date, end_date)

        if datetime_slot in analytics['datetime_slot_details']:
            return {
                'datetime_slot': datetime_slot,
                'subscribers': analytics['datetime_slot_details'][datetime_slot]
            }
        else:
            return {
                'datetime_slot': datetime_slot,
                'subscribers': {'sure': [], 'maybe': []}
            }


class Subscription(models.Model):
    NOTIFICATION_PREFERENCES = [
        ('all', 'All Events'),
        ('matching', 'Only Matching Schedule'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    notification_preference = models.CharField(max_length=20, choices=NOTIFICATION_PREFERENCES, default='all')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'organization']

    def __str__(self):
        return f"{self.user.username} - {self.organization.name}"


class AnonymousSubscription(models.Model):
    NOTIFICATION_PREFERENCES = [
        ('all', 'All Events'),
        ('matching', 'Only Matching Schedule'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone_number = models.CharField(max_length=20, blank=True)
    whatsapp_number = models.CharField(max_length=20, blank=True)
    notification_preference = models.CharField(max_length=20, choices=NOTIFICATION_PREFERENCES, default='all')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['email', 'organization']

    def __str__(self):
        return f"{self.name} ({self.email}) - {self.organization.name}"
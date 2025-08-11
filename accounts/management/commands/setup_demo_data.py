from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from organizations.models import Organization, Subscription
from events.models import Event, UserAvailability, EventResponse
from recurrence import Recurrence

User = get_user_model()

class Command(BaseCommand):
    help = 'Set up demo data for the Event Coordinator application'

    def handle(self, *args, **options):
        self.stdout.write('Setting up demo data...')
        
        # Create demo organizations
        org_user1 = User.objects.create_user(
            username='fitness_club',
            email='info@fitnessclub.com',
            password='demo123',
            user_type='organization'
        )
        
        org1 = Organization.objects.create(
            user=org_user1,
            name='Downtown Fitness Club',
            description='Your local fitness club offering various workout classes and training sessions.',
            notification_type='email',
            smtp_host='smtp.gmail.com',
            smtp_port=587,
            smtp_username='info@fitnessclub.com'
        )
        
        org_user2 = User.objects.create_user(
            username='book_club',
            email='organizer@bookclub.com',
            password='demo123',
            user_type='organization'
        )
        
        org2 = Organization.objects.create(
            user=org_user2,
            name='City Book Club',
            description='Monthly book discussions and literary events for book enthusiasts.',
            notification_type='email',
            smtp_host='smtp.gmail.com',
            smtp_port=587,
            smtp_username='organizer@bookclub.com'
        )
        
        # Create demo users
        user1 = User.objects.create_user(
            username='john_doe',
            email='john@example.com',
            password='demo123',
            phone_number='+1234567890',
            user_type='user'
        )
        
        user2 = User.objects.create_user(
            username='jane_smith',
            email='jane@example.com',
            password='demo123',
            phone_number='+1234567891',
            user_type='user'
        )
        
        # Create subscriptions
        Subscription.objects.create(user=user1, organization=org1, notification_preference='all')
        Subscription.objects.create(user=user1, organization=org2, notification_preference='matching')
        Subscription.objects.create(user=user2, organization=org1, notification_preference='matching')
        
        # Create demo events
        now = timezone.now()
        
        # Upcoming events
        event1 = Event.objects.create(
            organization=org1,
            title='Morning Yoga Session',
            description='Start your day with a relaxing yoga session suitable for all levels.',
            date_time=now + timedelta(days=2, hours=9),
            duration_hours=1.0,
            location='Studio A',
            notification_hours_before=24,
            max_participants=20
        )
        
        event2 = Event.objects.create(
            organization=org1,
            title='HIIT Training',
            description='High-intensity interval training for those looking for a challenging workout.',
            date_time=now + timedelta(days=5, hours=18),
            duration_hours=1.5,
            location='Gym Floor',
            notification_hours_before=12,
            max_participants=15
        )
        
        event3 = Event.objects.create(
            organization=org2,
            title='Monthly Book Discussion',
            description='Discussion of this month\'s selected book: "The Great Gatsby"',
            date_time=now + timedelta(days=7, hours=19),
            duration_hours=2.0,
            location='Community Center',
            notification_hours_before=48,
            max_participants=25
        )
        
        # Past events
        past_event = Event.objects.create(
            organization=org1,
            title='Pilates Workshop',
            description='Introduction to pilates techniques and movements.',
            date_time=now - timedelta(days=3, hours=10),
            duration_hours=2.0,
            location='Studio B',
            notification_hours_before=24,
            max_participants=12
        )
        
        # Create event responses
        EventResponse.objects.create(event=event1, user=user1, response='yes')
        EventResponse.objects.create(event=event1, user=user2, response='maybe')
        EventResponse.objects.create(event=event2, user=user1, response='no')
        EventResponse.objects.create(event=past_event, user=user1, response='yes')
        EventResponse.objects.create(event=past_event, user=user2, response='yes')
        
        self.stdout.write(
            self.style.SUCCESS('Demo data created successfully!')
        )
        self.stdout.write('Demo accounts created:')
        self.stdout.write('Organizations:')
        self.stdout.write('  - fitness_club / demo123')
        self.stdout.write('  - book_club / demo123')
        self.stdout.write('Users:')
        self.stdout.write('  - john_doe / demo123')
        self.stdout.write('  - jane_smith / demo123')
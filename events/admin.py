from django.contrib import admin
from .models import UserAvailability, Event, EventResponse, NotificationLog

@admin.register(UserAvailability)
class UserAvailabilityAdmin(admin.ModelAdmin):
    list_display = ('user', 'organization', 'availability_type', 'created_at')
    list_filter = ('availability_type', 'organization')
    search_fields = ('user__username', 'organization__name')

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'organization', 'date_time', 'is_active', 'created_at')
    list_filter = ('is_active', 'organization', 'date_time')
    search_fields = ('title', 'organization__name')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(EventResponse)
class EventResponseAdmin(admin.ModelAdmin):
    list_display = ('user', 'event', 'response', 'responded_at')
    list_filter = ('response', 'responded_at')
    search_fields = ('user__username', 'event__title')

@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'event', 'notification_type', 'success', 'sent_at')
    list_filter = ('notification_type', 'success', 'sent_at')
    search_fields = ('user__username', 'event__title')
# events/admin.py
from django.contrib import admin
from .models import Event, EventResponse


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'organization', 'start_datetime', 'end_datetime', 'is_active', 'created_at')
    list_filter = ('is_active', 'organization', 'start_datetime', 'notify_on_creation', 'notify_on_deletion')
    search_fields = ('title', 'organization__name', 'slug')
    readonly_fields = ('created_at', 'updated_at')  # Removed slug temporarily
    prepopulated_fields = {'slug': ('title',)}

    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'slug', 'organization', 'description', 'location')
        }),
        ('Date & Time', {
            'fields': ('start_datetime', 'end_datetime')
        }),
        ('Notification Settings', {
            'fields': ('notify_on_creation', 'notify_hours_before', 'notify_on_deletion')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(EventResponse)
class EventResponseAdmin(admin.ModelAdmin):
    list_display = ('get_responder', 'event', 'response', 'responded_at')
    list_filter = ('response', 'responded_at')
    search_fields = ('event__title', 'user__username', 'anonymous_subscription__name', 'anonymous_subscription__email')
    readonly_fields = ('responded_at',)

    def get_responder(self, obj):
        """Get the responder name (user or anonymous)"""
        if obj.user:
            return obj.user.username
        elif obj.anonymous_subscription:
            return f"{obj.anonymous_subscription.name} (Anonymous)"
        return "Unknown"

    get_responder.short_description = 'Responder'
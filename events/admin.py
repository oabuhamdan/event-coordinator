from django.contrib import admin
from .models import Event, EventResponse


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'organization', 'date_time', 'is_active', 'created_at')
    list_filter = ('is_active', 'organization', 'date_time')
    search_fields = ('title', 'organization__name')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(EventResponse)
class EventResponseAdmin(admin.ModelAdmin):
    list_display = ('get_responder', 'event', 'response', 'responded_at')
    list_filter = ('response', 'responded_at')
    search_fields = ('event__title', 'user__username', 'anonymous_subscription__name')

    def get_responder(self, obj):
        """Get the responder name (user or anonymous)"""
        if obj.user:
            return obj.user.username
        elif obj.anonymous_subscription:
            return f"{obj.anonymous_subscription.name} (Anonymous)"
        return "Unknown"
    get_responder.short_description = 'Responder'

from django.contrib import admin
from .models import NotificationLog


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ('recipient_name', 'event', 'notification_type', 'success', 'sent_at')
    list_filter = ('notification_type', 'success', 'sent_at')
    search_fields = ('user__username', 'event__title', 'anonymous_subscription__name', 'anonymous_subscription__email')
    readonly_fields = ('sent_at',)
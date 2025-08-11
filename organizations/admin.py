from django.contrib import admin
from .models import Organization, Subscription

@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'notification_type', 'created_at')
    list_filter = ('notification_type', 'created_at')
    search_fields = ('name', 'user__username')

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'organization', 'notification_preference', 'created_at')
    list_filter = ('notification_preference', 'created_at')
    search_fields = ('user__username', 'organization__name')
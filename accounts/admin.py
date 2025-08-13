from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, UserSession, UserAvailability

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'user_type', 'is_staff', 'date_joined')
    list_filter = ('user_type', 'is_staff', 'is_superuser', 'is_active')
    search_fields = ('username', 'email', 'phone_number')
    
    # Add user_type to the existing fieldsets
    fieldsets = BaseUserAdmin.fieldsets + (
        ('User Type', {'fields': ('user_type', 'phone_number', 'whatsapp_number', 'email_verified', 'phone_verified')}),
    )


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = ('get_user_info', 'ip_address', 'session_key', 'created_at', 'last_activity', 'is_active')
    list_filter = ('is_active', 'created_at', 'last_activity')
    search_fields = ('user__username', 'ip_address', 'session_key')
    readonly_fields = ('created_at', 'last_activity')

    def get_user_info(self, obj):
        """Get user information or show as anonymous"""
        if obj.user:
            return f"{obj.user.username} ({obj.user.get_user_type_display()})"
        return "Anonymous User"
    get_user_info.short_description = 'User'


@admin.register(UserAvailability)
class UserAvailabilityAdmin(admin.ModelAdmin):
    list_display = ('get_subscriber', 'organization', 'recurrence_type', 'availability_type', 'created_at')
    list_filter = ('availability_type', 'recurrence_type', 'organization')
    search_fields = ('user__username', 'anonymous_subscription__name', 'organization__name')
    readonly_fields = ('created_at', 'updated_at')

    def get_subscriber(self, obj):
        """Get subscriber name (user or anonymous)"""
        if obj.user:
            return obj.user.username
        elif obj.anonymous_subscription:
            return f"{obj.anonymous_subscription.name} (Anonymous)"
        return "Unknown"
    get_subscriber.short_description = 'Subscriber'

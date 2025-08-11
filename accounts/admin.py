from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'user_type', 'phone_number', 'is_active')
    list_filter = ('user_type', 'is_active', 'is_staff')
    search_fields = ('username', 'email', 'phone_number')
    
    fieldsets = UserAdmin.fieldsets + (
        ('Additional Info', {
            'fields': ('user_type', 'phone_number', 'whatsapp_number', 'email_verified', 'phone_verified')
        }),
    )
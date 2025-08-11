from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    USER_TYPE_CHOICES = [
        ('user', 'Regular User'),
        ('organization', 'Organization'),
    ]
    
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default='user')
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    whatsapp_number = models.CharField(max_length=20, blank=True, null=True)
    email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.username} ({self.get_user_type_display()})"
from django.urls import path, include
from django.contrib.auth import views as auth_views
from . import views

app_name = 'accounts'

urlpatterns = [
    # User registration and authentication
    path('register/user/', views.register_user, name='register_user'),
    path('register/organization/', views.register_organization, name='register_organization'),
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('profile/', views.profile, name='profile'),

    # Unified availability management
    path('availability/<int:organization_id>/', views.set_availability, name='set_availability'),

    # Legacy availability endpoints (will be removed)
    path('availability/set/<int:organization_id>/', views.set_availability, name='legacy_set_availability'),
    path('availability/anonymous/set/<int:organization_id>/', views.set_anonymous_availability, name='set_anonymous_availability'),
    path('availability/get/<int:organization_id>/', views.get_availability, name='get_availability'),

    # Anonymous user profile management
    path('anonymous/profile/<int:organization_id>/', views.anonymous_profile, name='anonymous_profile'),
]
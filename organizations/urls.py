from django.urls import path
from . import views

app_name = 'organizations'

urlpatterns = [
    # Organization listing and management
    path('', views.list_organizations, name='list'),
    path('create/', views.create_profile, name='create_profile'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('edit/', views.edit_profile, name='edit_profile'),
    path('subscribers/', views.subscribers, name='subscribers'),
    path('<str:username>/subscriber-availability/', views.get_subscriber_availability,
         name='subscriber_availability'),
    path('analytics/', views.availability_analytics, name='availability_analytics'),

    # Analytics endpoints
    path('<str:username>/datetime-slot-details/', views.get_datetime_slot_details, name='datetime_slot_details'),

    # Organization detail and subscription management
    path('<str:username>/', views.organization_detail, name='detail'),
    path('<str:username>/subscribe/', views.subscribe, name='subscribe'),
    path('<str:username>/unsubscribe/', views.unsubscribe, name='unsubscribe'),
    path('<str:username>/anonymous-subscribe/', views.anonymous_subscribe, name='anonymous_subscribe'),
]
# events/urls.py
from django.urls import path
from . import views

app_name = 'events'

urlpatterns = [
    # Event management under organization (username is already in main URL)
    path('', views.list_events, name='list'),
    path('create/', views.create_event, name='create'),
    path('<slug:slug>/', views.event_detail, name='detail'),
    path('<slug:slug>/edit/', views.edit_event, name='edit'),
    path('<slug:slug>/delete/', views.delete_event, name='delete'),
    path('<slug:slug>/respond/', views.respond_to_event, name='respond'),
    path('<slug:slug>/analytics/', views.event_analytics, name='analytics'),

    # API endpoints
    path('api/availability-slots/', views.get_availability_slots, name='api_availability_slots'),
]
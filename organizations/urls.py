from django.urls import path
from . import views

app_name = 'organizations'


urlpatterns = [
    path('', views.list_organizations, name='list'),
    path('create/', views.create_profile, name='create_profile'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('edit/', views.edit_profile, name='edit_profile'),
    path('subscribers/', views.subscribers, name='subscribers'),
    path('analytics/', views.availability_analytics, name='availability_analytics'),
    path('<int:organization_id>/time-slot-details/', views.get_time_slot_details, name='time_slot_details'),
    path('<int:organization_id>/datetime-slot-details/', views.get_datetime_slot_details, name='datetime_slot_details'),
    path('<int:pk>/', views.organization_detail, name='detail'),
    path('<int:pk>/subscribe/', views.subscribe, name='subscribe'),
    path('<int:pk>/unsubscribe/', views.unsubscribe, name='unsubscribe'),
    path('<int:pk>/anonymous-subscribe/', views.anonymous_subscribe, name='anonymous_subscribe'),
]
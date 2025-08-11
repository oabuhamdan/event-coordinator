from django.urls import path
from . import views

app_name = 'events'

urlpatterns = [
    path('', views.list_events, name='list'),
    path('create/', views.create_event, name='create'),
    path('<int:pk>/', views.event_detail, name='detail'),
    path('<int:pk>/edit/', views.edit_event, name='edit'),
    path('<int:pk>/delete/', views.delete_event, name='delete'),
    path('<int:pk>/respond/', views.respond_to_event, name='respond'),
    path('<int:pk>/analytics/', views.event_analytics, name='analytics'),
    path('availability/<int:organization_id>/', views.set_availability, name='set_availability'),
    path('availability/<int:organization_id>/<int:subscription_id>/anonymous/', views.set_anonymous_availability,
         name='set_anonymous_availability'),
]
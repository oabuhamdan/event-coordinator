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
    path('availability/<int:organization_id>/access/<str:token>/', views.anonymous_availability_access,
         name='anonymous_availability_access'),
    path('availability/<int:organization_id>/anonymous-email/', views.anonymous_availability_by_email,
         name='anonymous_availability_by_email'),
    path('subscribe-anonymous/<int:organization_id>/', views.subscribe_anonymous, name='subscribe_anonymous'),
]
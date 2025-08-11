from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api_views import EventResponseAPIView

router = DefaultRouter()

urlpatterns = [
    path('', include(router.urls)),
    path('events/<int:event_id>/respond/', EventResponseAPIView.as_view(), name='event_respond_api'),
]
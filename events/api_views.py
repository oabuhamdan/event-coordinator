from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from .models import Event, EventResponse
from organizations.models import Subscription

class EventResponseAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, event_id):
        event = get_object_or_404(Event, id=event_id)
        
        # Check if user is subscribed
        if not Subscription.objects.filter(user=request.user, organization=event.organization).exists():
            return Response(
                {'error': 'You must be subscribed to this organization to respond to events.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        response_value = request.data.get('response')
        if response_value not in ['yes', 'no', 'maybe']:
            return Response(
                {'error': 'Invalid response. Must be "yes", "no", or "maybe".'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        response_obj, created = EventResponse.objects.update_or_create(
            event=event,
            user=request.user,
            defaults={'response': response_value}
        )
        
        return Response({
            'message': 'Response recorded successfully',
            'response': response_obj.response,
            'created': created
        }, status=status.HTTP_200_OK)
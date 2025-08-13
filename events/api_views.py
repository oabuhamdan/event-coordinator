from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from .models import Event, EventResponse
from .services import EventService
from .utils import is_regular_user

class EventResponseAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, event_id):
        event = get_object_or_404(Event, id=event_id)
        
        # Use service layer for validation
        if not EventService.can_user_respond(request.user, event):
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
        
        # Get updated response counts using service
        response_counts = EventService.get_response_counts(event)

        return Response({
            'message': 'Response recorded successfully',
            'response': response_obj.response,
            'created': created,
            'response_counts': response_counts
        }, status=status.HTTP_200_OK)
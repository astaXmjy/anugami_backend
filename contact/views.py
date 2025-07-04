
# contact/views.py
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from .serializers import ContactSubmissionSerializer
from .models import ContactSubmission

@api_view(['POST'])
@permission_classes([AllowAny])
def contact_us(request):
    """
    Handle contact form submissions
    """
    serializer = ContactSubmissionSerializer(data=request.data)
    
    if serializer.is_valid():
        # Save the contact submission
        contact_submission = serializer.save()
        
        # If user is authenticated, link to their customer profile
        if request.user.is_authenticated and hasattr(request.user, 'customer'):
            contact_submission.customer = request.user.customer
            contact_submission.save()
        
        # Send email notification
        try:
            context = {
                'name': serializer.validated_data['name'],
                'email': serializer.validated_data['email'],
                'phone': serializer.validated_data['phone'],
                'subject': serializer.validated_data['subject'],
                'message': serializer.validated_data['message'],
            }
            
            # Use the template from email_templates app
            email_body = render_to_string('email_templates/customer_service/contact_us.html', context)
            
            send_mail(
                subject=f"Contact Form: {serializer.validated_data['subject']}",
                message=email_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[settings.CONTACT_EMAIL],
                html_message=email_body,
                fail_silently=False,
            )
        except Exception as e:
            print(f"Email sending failed: {str(e)}")
        
        return Response({
            'message': 'Contact form submitted successfully',
            'id': contact_submission.id
        }, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
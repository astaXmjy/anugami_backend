import random
import string
from django.core.cache import cache
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string

class EmailOTP:
    @staticmethod
    def generate_otp(length=6):
        """Generate a random OTP."""
        return ''.join(random.choices(string.digits, k=length))
    
    @staticmethod
    def store_otp(email, otp, timeout=300):
        """Store OTP in cache with 5 minutes expiry."""
        cache_key = f"email_otp_{email}"
        cache.set(cache_key, otp, timeout)
    
    @staticmethod
    def verify_otp(email, otp):
        """Verify the OTP for given email."""
        cache_key = f"email_otp_{email}"
        stored_otp = cache.get(cache_key)
        
        if not stored_otp:
            return False
        
        # Delete OTP after verification attempt
        cache.delete(cache_key)
        
        return stored_otp == otp
    
    @staticmethod
    def send_verification_email(email, otp):
        """Send OTP verification email."""
        print(email)
        try:
            # Render email template
            html_message = render_to_string('sellers/verification.html', {
                'otp': otp,
                'valid_minutes': 5
            })
            
            # Send email
            send_mail(
                subject='Email Verification OTP',
                message=f'Your verification code is: {otp}',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                html_message=html_message,
                fail_silently=False,
            )
            return True
        except Exception as e:
            print(f"Failed to send verification email: {str(e)}")
            return False
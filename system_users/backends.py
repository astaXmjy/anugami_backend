from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

User = get_user_model()

class CustomAuthBackend(ModelBackend):
    """
    Custom authentication backend that allows authentication 
    using email instead of username
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            user = User.objects.get(email=username)
            if user.check_password(password):
                return user
            return None
        except User.DoesNotExist:
            return None

    def get_user(self, user_id):
        """
        Override get_user method to use our custom user model
        """
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
        
class EmailBackend(CustomAuthBackend):
    """
    Alias for CustomAuthBackend to match the expected backend name
    """
    pass        
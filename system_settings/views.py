# views.py
from rest_framework import viewsets, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework import status
from .models import (
    SystemSetting, 
    EmailSetting, 
    ContactInfo, 
    Policy, 
    WebSetting, 
    FirebaseSetting, 
    PickupLocation,
    HeroSlide,
    BannerSection,
    BannerItem
)
from .serializers import (
    SystemSettingSerializer, 
    EmailSettingSerializer, 
    ContactInfoSerializer,
    PolicySerializer, 
    WebSettingSerializer, 
    FirebaseSettingSerializer, 
    PickupLocationSerializer,
    HeroSlideSerializer,
    BannerSectionSerializer,
    BannerItemSerializer,
    BannerSectionPublicSerializer,
    FrontendBannerSectionSerializer
)

class SystemSettingViewSet(viewsets.ModelViewSet):
    """Handles System Settings"""
    queryset = SystemSetting.objects.all()
    serializer_class = SystemSettingSerializer

class EmailSettingViewSet(viewsets.ModelViewSet):
    """Handles Email Settings"""
    queryset = EmailSetting.objects.all()
    serializer_class = EmailSettingSerializer

class ContactInfoViewSet(viewsets.ModelViewSet):
    """Handles Contact Information"""
    queryset = ContactInfo.objects.all()
    serializer_class = ContactInfoSerializer

class PolicyViewSet(viewsets.ModelViewSet):
    """Handles various policies"""
    queryset = Policy.objects.all()
    serializer_class = PolicySerializer

class WebSettingViewSet(viewsets.ModelViewSet):
    """Handles Web Settings"""
    queryset = WebSetting.objects.all()
    serializer_class = WebSettingSerializer

class FirebaseSettingViewSet(viewsets.ModelViewSet):
    """Handles Firebase Settings"""
    queryset = FirebaseSetting.objects.all()
    serializer_class = FirebaseSettingSerializer

class PickupLocationViewSet(viewsets.ModelViewSet):
    """Handles Pickup Locations"""
    queryset = PickupLocation.objects.all()
    serializer_class = PickupLocationSerializer

class HeroSlideViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing Hero Slides
    """
    queryset = HeroSlide.objects.all().order_by('display_order')
    serializer_class = HeroSlideSerializer
    
    def get_permissions(self):
        """
        Custom permissions:
        - Admin-only access for create, update, delete
        - Public access for listing slides
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [permissions.IsAdminUser]
        else:
            permission_classes = [permissions.AllowAny]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """
        Filter active slides for public endpoints
        """
        if self.request.user.is_staff:
            return HeroSlide.objects.all().order_by('display_order')
        return HeroSlide.objects.filter(is_active=True).order_by('display_order')
    
    @action(detail=False, methods=['get'], permission_classes=[permissions.AllowAny])
    def public(self, request):
        """
        Endpoint for public access to active slides
        """
        queryset = HeroSlide.objects.filter(is_active=True).order_by('display_order')
        serializer = self.get_serializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)

class BannerSectionViewSet(viewsets.ModelViewSet):
    """ViewSet for managing banner sections"""
    queryset = BannerSection.objects.all()
    serializer_class = BannerSectionSerializer
    
    def get_permissions(self):
        """
        Admin-only access for create, update, delete operations
        Public access for listing and retrieval
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [permissions.IsAdminUser]
        else:
            permission_classes = [permissions.AllowAny]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """Filter by active status for non-admin users"""
        if self.request.user.is_staff:
            return BannerSection.objects.all().order_by('display_order')
        return BannerSection.objects.filter(is_active=True).order_by('display_order')
    
    def get_serializer_class(self):
        """Use different serializers based on the action"""
        if self.action == 'public':
            return BannerSectionPublicSerializer
        if self.action == 'frontend_format':
            return FrontendBannerSectionSerializer
        return self.serializer_class
    
    @action(detail=False, methods=['get'], permission_classes=[permissions.AllowAny])
    def public(self, request):
        """Endpoint for public access to active banner sections"""
        queryset = BannerSection.objects.filter(is_active=True).order_by('display_order')
        serializer = self.get_serializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[permissions.AllowAny])
    def frontend_format(self, request):
        """Endpoint that returns data in a format ready for frontend components"""
        queryset = BannerSection.objects.filter(is_active=True).order_by('display_order')
        
        # Filter by section_type if provided
        section_type = request.query_params.get('type', None)
        if section_type:
            queryset = queryset.filter(section_type=section_type)
        
        # Get a specific section by name
        section_name = request.query_params.get('name', None)
        if section_name:
            queryset = queryset.filter(name=section_name)
        
        serializer = self.get_serializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)

class BannerItemViewSet(viewsets.ModelViewSet):
    """ViewSet for managing banner items"""
    queryset = BannerItem.objects.all()
    serializer_class = BannerItemSerializer
    
    def get_permissions(self):
        """Allow read access to anyone, but restrict write ops to admin users"""
        if self.action in ['list', 'retrieve', 'by_section']:
            permission_classes = [permissions.AllowAny]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def create(self, request, *args, **kwargs):
        """Handle creating banner items with file uploads via FormData"""
        # Print the request data for debugging
        print("Request data keys:", request.data.keys())
        print("Section ID from request:", request.data.get('section'))
        
        # Validate section_id is present
        if 'section' not in request.data or not request.data.get('section'):
            return Response(
                {"error": "Section ID is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create a mutable copy of the data
        data = request.data.copy()
        
        # Ensure section is correctly formatted (should be an integer)
        try:
            section_id = int(data.get('section'))
            # Check if the section exists in the database
            section = BannerSection.objects.get(id=section_id)
            # If we get here, the section exists
        except (ValueError, TypeError):
            return Response(
                {"error": f"Invalid section ID format: {data.get('section')}"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        except BannerSection.DoesNotExist:
            return Response(
                {"error": f"Section with ID {section_id} does not exist"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Continue with normal processing
        serializer = self.get_serializer(data=data)
        
        if not serializer.is_valid():
            print("Serializer errors:", serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    
    def update(self, request, *args, **kwargs):
        """Handle updating banner items with file uploads via FormData"""
        # Print the request data for debugging
        print("Update data keys:", request.data.keys())
        
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        # Create a mutable copy of the data
        data = request.data.copy()
        
        # If section is provided, ensure it's valid
        if 'section' in data and data['section']:
            try:
                section_id = int(data.get('section'))
                # Check if the section exists in the database
                section = BannerSection.objects.get(id=section_id)
                # If we get here, the section exists
            except (ValueError, TypeError):
                return Response(
                    {"error": f"Invalid section ID format: {data.get('section')}"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            except BannerSection.DoesNotExist:
                return Response(
                    {"error": f"Section with ID {section_id} does not exist"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        elif 'section' in data and not data['section']:
            # Remove empty section to keep the existing one
            data.pop('section')
            
        serializer = self.get_serializer(instance, data=data, partial=partial)
        
        if not serializer.is_valid():
            print("Serializer update errors:", serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        self.perform_update(serializer)
        
        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}
            
        return Response(serializer.data)
        
    @action(detail=False, methods=['get'], url_path='by-section/(?P<section_id>[^/.]+)')
    def by_section(self, request, section_id=None):
        """Get all banner items for a specific section"""
        banners = BannerItem.objects.filter(section_id=section_id).order_by('display_order')
        serializer = self.get_serializer(banners, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'], url_path='update-order')
    def update_order(self, request):
        """Update the display order of multiple banner items at once"""
        data = request.data
        if not isinstance(data, list):
            return Response({"error": "Expected a list of items"}, status=status.HTTP_400_BAD_REQUEST)
        
        for item in data:
            try:
                banner = BannerItem.objects.get(id=item['id'])
                banner.display_order = item['display_order']
                banner.save(update_fields=['display_order'])
            except (BannerItem.DoesNotExist, KeyError):
                pass
        
        return Response({"status": "Orders updated successfully"})
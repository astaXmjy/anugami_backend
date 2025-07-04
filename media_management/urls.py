from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import MediaViewSet

app_name = 'media_management'

router = DefaultRouter()
router.register(r'media', MediaViewSet, basename='media')

urlpatterns = [
    path('', include(router.urls)),
]

# Available URLs:
# GET/POST /media/ - List all media or create new
# GET/DELETE /media/{id}/ - Retrieve or delete specific media
# POST /media/{id}/attach_to_product/ - Attach media to product
# POST /media/{id}/attach_to_category/ - Attach media to category
# GET /media/{id}/products/ - List all products using this media
# GET /media/{id}/categories/ - List all categories using this media
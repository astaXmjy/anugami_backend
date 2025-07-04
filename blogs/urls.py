from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    BlogPostViewSet,
    BlogCategoryViewSet,
    BlogCommentViewSet,
    BlogTagViewSet,
    upload_ckeditor_image
)
from django.conf import settings
from django.conf.urls.static import static

app_name = 'blogs'

router = DefaultRouter()
router.register(r'posts', BlogPostViewSet, basename='post')
router.register(r'categories', BlogCategoryViewSet, basename='category')
router.register(r'comments', BlogCommentViewSet, basename='comment')
router.register(r'tags', BlogTagViewSet, basename='tag')

urlpatterns = [
    # API Endpoints
    path('', include(router.urls)),
    
    # CKEditor Image Upload
    path('upload-ckeditor-image/', upload_ckeditor_image, name='upload_ckeditor_image'),
]

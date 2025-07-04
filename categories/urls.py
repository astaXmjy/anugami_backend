# categories/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CategoryViewSet, CategoryRequestViewSet

app_name = "categories"

router = DefaultRouter()
router.register(r"categories", CategoryViewSet, basename="category")
router.register(r"requests", CategoryRequestViewSet, basename="category-request")

urlpatterns = [
    path("", include(router.urls)),
    path("tree/", CategoryViewSet.as_view({"get": "tree"}), name="category-tree"),
    path(
        "move/<slug:slug>/",
        CategoryViewSet.as_view({"post": "move"}),
        name="category-move",
    ),
    path(
        "bulk-action/",
        CategoryViewSet.as_view({"post": "bulk_action"}),
        name="category-bulk-action",
    ),
    path(
        "upload-image/<slug:slug>/",
        CategoryViewSet.as_view({"post": "upload_image"}),
        name="category-upload-image",
    ),
    path(
        "delete-image/<slug:slug>/<int:image_id>/",
        CategoryViewSet.as_view({"delete": "delete_image"}),
        name="category-delete-image",
    ),
    path(
        "descendants/<slug:slug>/",
        CategoryViewSet.as_view({"get": "descendants"}),
        name="category-descendants",
    ),
    path(
        "ancestors/<slug:slug>/",
        CategoryViewSet.as_view({"get": "ancestors"}),
        name="category-ancestors",
    ),
]
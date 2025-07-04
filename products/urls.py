from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    BrandViewSet,
    BulkCreateProductsView,
    BulkDownloadProductsView,
    BulkUpdateProductsView,
    ProductReviewViewSet,
    ProductVariantViewSet,
    ProductStockViewSet,
    ProductViewSet,
    ProductAttributeViewSet,
    ProductFeatureRequestViewSet,
    hsn_code_list,
    sac_code_list,
    set_primary_image,
)

app_name = "products"

router = DefaultRouter()
router.register(r"products", ProductViewSet, basename="products")
router.register(r"reviews", ProductReviewViewSet, basename="review")
router.register(r"stock", ProductStockViewSet, basename="stock")
router.register(r"brands", BrandViewSet, basename="brand")
router.register(r"attributes", ProductAttributeViewSet, basename="attribute")
router.register(
    r"feature-requests", ProductFeatureRequestViewSet, basename="feature-request"
)

urlpatterns = [
    path("", include(router.urls)),
    # Custom endpoints
    path(
        "featured/",
        ProductViewSet.as_view({"get": "featured"}, basename="products"),
        name="featured-products",
    ),
    path(
        "create-product/",
        ProductViewSet.as_view({"post": "create_product"}, basename="products"),
        name="create-product",
    ),
    path(
        "seller/",
        ProductViewSet.as_view({"get": "seller_products"}, basename="products"),
        name="seller-products",
    ),
    path(
        "by-category-tree/",
        ProductViewSet.as_view({"get": "by_category_tree"}, basename="products"),
        name="products-by-category-tree",
    ),
    path(
        "search/",
        ProductViewSet.as_view({"get": "search"}),
        name="products-search",
    ),
    # Product availability and stock
    path(
        "<slug:slug>/availability/",
        ProductViewSet.as_view({"get": "availability"}, basename="products"),
        name="product-availability",
    ),
    path(
        "<slug:slug>/stock-alert/",
        ProductViewSet.as_view({"get": "stock_alert"}, basename="products"),
        name="product-stock-alert",
    ),
    # Image management
    path(
        "<slug:slug>/upload-images/",
        ProductViewSet.as_view({"post": "upload_images"}, basename="products"),
        name="product-upload-images",
    ),
    path(
        "<int:pk>/upload-images/",
        ProductViewSet.as_view({"post": "upload_images"}),
        name="product-upload-images-by-id",
    ),
    path(
        "<slug:slug>/delete-image/",
        ProductViewSet.as_view({"delete": "delete_image"}, basename="products"),
        name="delete-image",
    ),
    path(
        "<slug:slug>/delete-all-images/",
        ProductViewSet.as_view({"delete": "delete_all_images"}, basename="products"),
        name="delete-all-images",
    ),
    path("<slug:slug>/set-primary-image/", set_primary_image, name="set-primary-image"),
    # Video management
    path(
        "<slug:slug>/upload-videos/",
        ProductViewSet.as_view({"post": "upload_videos"}, basename="products"),
        name="product-upload-videos",
    ),
    path(
        "<slug:slug>/delete-video/",
        ProductViewSet.as_view({"delete": "delete_video"}, basename="products"),
        name="delete-video",
    ),
    path(
        "<slug:slug>/set-featured-video/",
        ProductViewSet.as_view({"post": "set_featured_video"}, basename="products"),
        name="set-featured-video",
    ),
    # Shipping policy
    path(
        "<slug:slug>/assign_shipping_policy/",
        ProductViewSet.as_view({"post": "assign_shipping_policy"}, basename="products"),
        name="product-assign-shipping-policy",
    ),
    # Product variants
    path(
        "<slug:slug>/variants/",
        ProductViewSet.as_view({"get": "variants"}, basename="products"),
        name="product-variants",
    ),
    path(
        "<slug:slug>/variant-matrix/",
        ProductViewSet.as_view({"get": "variant_matrix"}, basename="products"),
        name="product-variant-matrix",
    ),
    path(
        "<slug:slug>/color-images/",
        ProductViewSet.as_view({"get": "color_images"}, basename="products"),
        name="product-color-images",
    ),
    path(
        "<slug:slug>/upload-color-images/",
        ProductViewSet.as_view({"post": "upload_color_images"}, basename="products"),
        name="product-upload-color-images",
    ),
    path(
        "<slug:slug>/create-variant/",
        ProductViewSet.as_view({"post": "create_variant"}, basename="products"),
        name="product-create-variant",
    ),
    path(
        "<slug:slug>/bulk-create-variants/",
        ProductViewSet.as_view({"post": "bulk_create_variants"}, basename="products"),
        name="product-bulk-create-variants",
    ),
    path(
        "<slug:slug>/available-options/",
        ProductViewSet.as_view({"get": "available_options"}, basename="products"),
        name="product-available-options",
    ),
    path(
        "<slug:slug>/check-variant-availability/",
        ProductViewSet.as_view(
            {"get": "check_variant_availability"}, basename="products"
        ),
        name="product-check-variant-availability",
    ),
    path(
        "<slug:slug>/variant/<slug:variant_slug>/",
        ProductViewSet.as_view({"get": "variant_detail"}, basename="products"),
        name="product-variant-detail",
    ),
    path(
        "mobile-variant-selector/<slug:slug>/",
        ProductViewSet.as_view({"get": "mobile_variant_selector"}, basename="products"),
        name="mobile-variant-selector",
    ),
    # Product tracking and viewing
    path(
        "track-product-view/<slug:slug>/",
        ProductViewSet.as_view({"post": "track_product_view"}, basename="products"),
        name="track-product-view",
    ),
    path(
        "recently-viewed/",
        ProductViewSet.as_view({"get": "recently_viewed"}, basename="products"),
        name="recently-viewed-products",
    ),
    path(
        "complementary-products/",
        ProductViewSet.as_view({"get": "complementary_products"}, basename="products"),
        name="complementary-products",
    ),
    # Bulk operations
    path(
        "bulk-update/",
        BulkUpdateProductsView.as_view(),
        name="bulk-update-products",
    ),
    path(
        "bulk-download/",
        BulkDownloadProductsView.as_view(),
        name="bulk-download-products",
    ),
    path(
        "bulk-create/",
        BulkCreateProductsView.as_view(),
        name="bulk-create-products",
    ),
    path(
        "bulk-update-variant-stock/",
        ProductViewSet.as_view(
            {"post": "bulk_update_variant_stock"}, basename="products"
        ),
        name="bulk-update-variant-stock",
    ),
    # Tax codes
    path("hsn-codes/", hsn_code_list, name="hsn-codes"),
    path("sac-codes/", sac_code_list, name="sac-codes"),
    # Brand management
    path(
        "brands/<slug:slug>/upload-logo/",
        BrandViewSet.as_view({"post": "upload_logo"}, basename="brands"),
        name="brand-upload-logo",
    ),
    path(
        "brands/<slug:slug>/delete-logo/",
        BrandViewSet.as_view({"delete": "delete_logo"}, basename="brands"),
        name="brand-delete-logo",
    ),
    path(
        "variants/<int:pk>/",
        ProductVariantViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="variant-detail",
    ),
    # Variant stock update
    path(
        "variants/<int:pk>/update-stock/",
        ProductVariantViewSet.as_view({"patch": "update_stock"}),
        name="variant-update-stock",
    ),
    # Toggle variant status
    path(
        "variants/<int:pk>/toggle-active/",
        ProductVariantViewSet.as_view({"post": "toggle_active"}),
        name="variant-toggle-active",
    ),
]

# categories/serializers.py
from rest_framework import serializers
from django.core.exceptions import ValidationError
from .models import Category, CategoryImage, CategorySEO, CategoryAttribute, CategoryRequest

class CategoryImageSerializer(serializers.ModelSerializer):
    """Serializer for category images using Firebase Storage"""
    image_file = serializers.FileField(write_only=True, required=False)
    
    class Meta:
        model = CategoryImage
        fields = [
            'id', 'image_url', 'image_file', 'alt_text',
            'is_primary', 'sort_order', 'width', 'height', 
            'file_size', 'created_at'
        ]
        read_only_fields = ['image_url', 'width', 'height', 'file_size', 'created_at']

class CategorySEOSerializer(serializers.ModelSerializer):
    """Serializer for category SEO settings"""
    class Meta:
        model = CategorySEO
        fields = [
            'page_title', 'meta_description', 'meta_keywords',
            'og_title', 'og_description', 'og_image', 'canonical_url',
            'robots_meta', 'schema_markup'
        ]

class CategoryAttributeSerializer(serializers.ModelSerializer):
    """Serializer for category attributes"""
    class Meta:
        model = CategoryAttribute
        fields = [
            'id', 'name', 'type', 'is_required', 'is_filter',
            'filter_type', 'options', 'validation', 'default_value',
            'sort_order', 'help_text'
        ]

class CategoryMinimalSerializer(serializers.ModelSerializer):
    """Minimal category representation"""
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug']

class CategoryBreadcrumbSerializer(serializers.ModelSerializer):
    """Serializer for category breadcrumbs"""
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug']

class CategoryTreeSerializer(serializers.ModelSerializer):
    """Serializer for nested category tree"""
    children = serializers.SerializerMethodField()
    level = serializers.IntegerField(read_only=True)
    parent_id = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Category
        fields = [
            'id', 'name', 'slug', 'level', 'parent_id',
            'is_active', 'is_featured', 'menu_order',
            'image_url', 'product_count', 'children'
        ]

    def get_children(self, obj):
        return CategoryTreeSerializer(
            obj.get_children().order_by('menu_order'),
            many=True
        ).data

class CategoryListSerializer(serializers.ModelSerializer):
    """Serializer for category list view"""
    parent_details = serializers.SerializerMethodField()
    children_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = [
            'id', 'name', 'slug', 'parent_details',
            'is_active', 'is_featured', 'product_count',
            'children_count', 'menu_order', 'image_url',
            'created_at'
        ]

    def get_parent_details(self, obj):
        if obj.parent:
            return {
                'id': str(obj.parent.id),
                'name': obj.parent.name,
                'slug': obj.parent.slug
            }
        return None

    def get_children_count(self, obj):
        return obj.get_children().count()

class CategoryMoveSerializer(serializers.Serializer):
    """Serializer for moving categories in the tree"""
    target_id = serializers.UUIDField(required=True)
    position = serializers.ChoiceField(
        choices=['first-child', 'last-child', 'left', 'right'],
        required=True
    )

class CategoryBulkActionSerializer(serializers.Serializer):
    """Serializer for bulk category actions"""
    ids = serializers.ListField(child=serializers.IntegerField())
    action = serializers.ChoiceField(
        choices=['activate', 'deactivate', 'delete', 'move']
    )
    target_id = serializers.IntegerField(required=False)
    position = serializers.ChoiceField(
        choices=['first-child', 'last-child', 'left', 'right'],
        required=False
    )

class CategoryDetailSerializer(serializers.ModelSerializer):
    """Main serializer for category detail"""
    parent = CategoryBreadcrumbSerializer(read_only=True)
    parent_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        required=False,
        allow_null=True,
        source='parent'
    )
    images = CategoryImageSerializer(many=True, read_only=True)
    seo = CategorySEOSerializer(required=False)
    attributes = CategoryAttributeSerializer(many=True, read_only=True)
    breadcrumb = serializers.SerializerMethodField()
    children = CategoryListSerializer(many=True, read_only=True)
    image_file = serializers.FileField(write_only=True, required=False)
    icon_file = serializers.FileField(write_only=True, required=False)
    banner_file = serializers.FileField(write_only=True, required=False)

    class Meta:
        model = Category
        fields = [
            'id', 'name', 'slug', 'description', 'short_description',
            'parent', 'parent_id', 'is_active', 'is_featured', 
            'show_in_menu', 'menu_order', 'display_order',
            'product_count', 'subcategory_count',
            'gst_rate', 'commission_rate', 'image_url', 
            'icon_url', 'banner_url', 'custom_url', 
            'redirect_url', 'image_file', 'icon_file', 
            'banner_file', 'images', 'seo', 'attributes',
            'breadcrumb', 'children', 'created_at',
            'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = [
            'slug', 'product_count', 'subcategory_count',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]

    def get_breadcrumb(self, obj):
        """Get category breadcrumb trail"""
        ancestors = obj.get_ancestors(include_self=True)
        return CategoryBreadcrumbSerializer(ancestors, many=True).data

    def validate(self, data):
        """Custom validation for category data"""
        # Validate name
        if 'name' in data and len(data['name']) < 2:
            raise ValidationError("Name must be at least 2 characters long")

        # Prevent self-referential parent
        if 'parent' in data and data['parent'] == self.instance:
            raise ValidationError("Category cannot be its own parent")

        return data

    def _handle_image_upload(self, category, image_file, image_type):
        """Helper method to handle image upload"""
        from .services import CategoryService
        if image_file:
            service = CategoryService()
            result = service.handle_category_image(
                str(category.id),
                image_file,
                size_preset=image_type
            )
            if result:
                return result['url']
        return None

    def create(self, validated_data):
        # Extract file data
        image_file = validated_data.pop("image_file", None)
        icon_file = validated_data.pop("icon_file", None)
        banner_file = validated_data.pop("banner_file", None)
        seo_data = validated_data.pop("seo", None)

        # Create category
        category = super().create(validated_data)

        # Handle file uploads
        if image_file:
            category.image_url = self._handle_image_upload(
                category, image_file, "medium"
            )
        if icon_file:
            category.icon_url = self._handle_image_upload(
                category, icon_file, "thumbnail"
            )
        if banner_file:
            category.banner_url = self._handle_image_upload(
                category, banner_file, "large"
            )

        # Save if any files were uploaded
        if any([image_file, icon_file, banner_file]):
            category.save()

        # Create SEO data if provided
        if seo_data:
            CategorySEO.objects.create(category=category, **seo_data)

        return category

    def update(self, instance, validated_data):
        # Extract file data
        image_file = validated_data.pop("image_file", None)
        icon_file = validated_data.pop("icon_file", None)
        banner_file = validated_data.pop("banner_file", None)
        seo_data = validated_data.pop("seo", None)

        # Update category
        category = super().update(instance, validated_data)

        # Handle file uploads
        if image_file:
            category.image_url = self._handle_image_upload(
                category, image_file, "medium"
            )
        if icon_file:
            category.icon_url = self._handle_image_upload(
                category, icon_file, "thumbnail"
            )
        if banner_file:
            category.banner_url = self._handle_image_upload(
                category, banner_file, "large"
            )

        # Save if any files were uploaded
        if any([image_file, icon_file, banner_file]):
            category.save()

        # Update SEO data if provided
        if seo_data and hasattr(category, "seo"):
            for key, value in seo_data.items():
                setattr(category.seo, key, value)
            category.seo.save()
        elif seo_data:
            CategorySEO.objects.create(category=category, **seo_data)

        return category

class CategoryRequestSerializer(serializers.ModelSerializer):
    """Serializer for category requests"""
    parent_details = serializers.SerializerMethodField()
    requested_by_details = serializers.SerializerMethodField()
    reviewed_by_details = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = CategoryRequest
        fields = [
            'id', 'name', 'description', 'parent', 'parent_details',
            'requested_by', 'requested_by_details', 'status', 'status_display',
            'admin_notes', 'reviewed_by', 'reviewed_by_details', 
            'reviewed_at', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'requested_by', 'status', 'admin_notes', 
            'reviewed_by', 'reviewed_at', 'created_at', 'updated_at'
        ]
    
    def get_parent_details(self, obj):
        if obj.parent:
            return {
                'id': str(obj.parent.id),
                'name': obj.parent.name,
                'slug': obj.parent.slug
            }
        return None
    
    def get_requested_by_details(self, obj):
        return {
            'id': str(obj.requested_by.id),
            'email': obj.requested_by.email,
            'name': obj.requested_by.name if hasattr(obj.requested_by, 'name') else obj.requested_by.email
        }
    
    def get_reviewed_by_details(self, obj):
        if obj.reviewed_by:
            return {
                'id': str(obj.reviewed_by.id),
                'email': obj.reviewed_by.email,
                'name': obj.reviewed_by.name if hasattr(obj.reviewed_by, 'name') else obj.reviewed_by.email
            }
        return None
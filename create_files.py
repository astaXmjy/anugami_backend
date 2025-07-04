# create_product_files_django.py
import os

BASE_DIR = './Anugami_backend/products'

def create_dir(dir_path):
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
        print(f"Created directory: {dir_path}")

def create_file(file_path, content=''):
    if not os.path.exists(file_path):
        with open(file_path, 'w') as f:
            f.write(content)
        print(f"Created file: {file_path}")

# Create main directories
directories = [
    'api',
    'models',
    'serializers',
    'services',
    'tests',
    'utils',
    'views'
]

for dir in directories:
    create_dir(os.path.join(BASE_DIR, dir))

# Create Django files
files = {
    'models/product.py': '''from django.db import models
from django.utils.translation import gettext_lazy as _

class Product(models.Model):
    name = models.CharField(_("Name"), max_length=255)
    slug = models.SlugField(_("Slug"), max_length=255, unique=True)
    description = models.TextField(_("Description"), blank=True)
    is_active = models.BooleanField(_("Active"), default=True)
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)

    class Meta:
        verbose_name = _("Product")
        verbose_name_plural = _("Products")
        ordering = ["-created_at"]

    def __str__(self):
        return self.name
''',

    'serializers/product.py': '''from rest_framework import serializers
from ..models import Product

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = '__all__'
''',

    'views/product.py': '''from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from ..models import Product
from ..serializers import ProductSerializer

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]
''',

    'services/product_service.py': '''from django.db.models import Q
from ..models import Product

class ProductService:
    @staticmethod
    def get_products(filters=None):
        queryset = Product.objects.all()
        if filters:
            # Add filter logic here
            pass
        return queryset

    @staticmethod
    def create_product(data):
        return Product.objects.create(**data)

    @staticmethod
    def update_product(product_id, data):
        product = Product.objects.get(id=product_id)
        for key, value in data.items():
            setattr(product, key, value)
        product.save()
        return product

    @staticmethod
    def delete_product(product_id):
        Product.objects.filter(id=product_id).delete()
''',

    'api/urls.py': '''from django.urls import path, include
from rest_framework.routers import DefaultRouter
from ..views import ProductViewSet

router = DefaultRouter()
router.register(r'products', ProductViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
''',

    'tests/test_products.py': '''from django.test import TestCase
from ..models import Product

class ProductTests(TestCase):
    def setUp(self):
        Product.objects.create(
            name="Test Product",
            slug="test-product",
            description="Test Description"
        )

    def test_product_creation(self):
        product = Product.objects.get(name="Test Product")
        self.assertEqual(product.slug, "test-product")
''',

    'utils/helpers.py': '''from django.utils.text import slugify

def generate_unique_slug(model_instance, slugable_field_name, slug_field_name):
    """
    Generate unique slug for a model instance
    """
    slug = slugify(getattr(model_instance, slugable_field_name))
    unique_slug = slug
    extension = 1
    ModelClass = model_instance.__class__

    while ModelClass._default_manager.filter(**{slug_field_name: unique_slug}).exists():
        unique_slug = '{}-{}'.format(slug, extension)
        extension += 1

    return unique_slug
'''
}

# Create all files
for file_path, content in files.items():
    create_file(os.path.join(BASE_DIR, file_path), content)

print("Django files creation completed successfully!")
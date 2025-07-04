# test_products_categories.py
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase, APIClient
from categories.models import Category, CategoryImage, CategoryAttribute
from products.models import Product, Brand, ProductImage, ProductReview
from categories.services import CategoryService
from products.services import ProductService
import uuid

User = get_user_model()

class BaseTestCase(TestCase):
    def setUp(self):
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

class CategoryModelTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.category = Category.objects.create(
            name='Test Category',
            description='Test Description'
        )

    def test_category_creation(self):
        """Test category creation and slug generation"""
        self.assertEqual(self.category.name, 'Test Category')
        self.assertTrue(self.category.slug)
        self.assertEqual(self.category.slug, 'test-category')

    def test_unique_slug_generation(self):
        """Test that duplicate category names get unique slugs"""
        category2 = Category.objects.create(
            name='Test Category'
        )
        self.assertNotEqual(self.category.slug, category2.slug)

    def test_category_str(self):
        """Test category string representation"""
        self.assertEqual(str(self.category), 'Test Category')

class CategoryServiceTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.service = CategoryService()
        self.category = Category.objects.create(
            name='Test Category',
            description='Test Description'
        )

    def test_get_category_by_id(self):
        """Test retrieving category by ID"""
        retrieved = self.service.get_category_by_id(self.category.id)
        self.assertEqual(retrieved, self.category)

    def test_get_category_tree(self):
        """Test getting category tree"""
        child = Category.objects.create(
            name='Child Category',
            parent=self.category
        )
        tree = self.service.get_category_tree()
        self.assertTrue(len(tree) > 0)

class ProductModelTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.category = Category.objects.create(
            name='Test Category'
        )
        self.brand = Brand.objects.create(
            name='Test Brand'
        )
        self.product = Product.objects.create(
            name='Test Product',
            description='Test Description',
            category=self.category,
            brand=self.brand,
            seller=self.user,
            regular_price=99.99,
            stock_quantity=10
        )

    def test_product_creation(self):
        """Test product creation and slug generation"""
        self.assertEqual(self.product.name, 'Test Product')
        self.assertTrue(self.product.slug)
        self.assertEqual(self.product.slug, 'test-product')

    def test_product_pricing(self):
        """Test product pricing calculations"""
        self.product.sale_price = 79.99
        self.product.save()
        self.assertEqual(float(self.product.regular_price), 99.99)
        self.assertEqual(float(self.product.sale_price), 79.99)

    def test_stock_management(self):
        """Test product stock management"""
        initial_stock = self.product.stock_quantity
        self.product.stock_quantity -= 5
        self.product.save()
        self.assertEqual(self.product.stock_quantity, initial_stock - 5)

class ProductAPITest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        self.category = Category.objects.create(
            name='Test Category'
        )
        self.brand = Brand.objects.create(
            name='Test Brand'
        )
        self.product = Product.objects.create(
            name='Test Product',
            description='Test Description',
            category=self.category,
            brand=self.brand,
            seller=self.user,
            regular_price=99.99,
            stock_quantity=10
        )

    def test_product_list(self):
        """Test product list endpoint"""
        url = reverse('products:product-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(len(response.data['results']) > 0)

    def test_product_create(self):
        """Test product creation endpoint"""
        url = reverse('products:product-list')
        data = {
            'name': 'New Product',
            'description': 'New Description',
            'category': self.category.id,
            'brand': self.brand.id,
            'regular_price': 149.99,
            'stock_quantity': 20
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'New Product')

    def test_product_update(self):
        """Test product update endpoint"""
        url = reverse('products:product-detail', kwargs={'slug': self.product.slug})
        data = {
            'name': 'Updated Product',
            'regular_price': 199.99
        }
        response = self.client.patch(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Updated Product')

class CategoryAPITest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        self.category = Category.objects.create(
            name='Test Category',
            description='Test Description'
        )

    def test_category_list(self):
        """Test category list endpoint"""
        url = reverse('categories:category-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(len(response.data['results']) > 0)

    def test_category_create(self):
        """Test category creation endpoint"""
        url = reverse('categories:category-list')
        data = {
            'name': 'New Category',
            'description': 'New Description'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'New Category')

    def test_category_update(self):
        """Test category update endpoint"""
        url = reverse('categories:category-detail', kwargs={'slug': self.category.slug})
        data = {
            'name': 'Updated Category'
        }
        response = self.client.patch(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Updated Category')

class ProductReviewTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.category = Category.objects.create(name='Test Category')
        self.brand = Brand.objects.create(name='Test Brand')
        self.product = Product.objects.create(
            name='Test Product',
            category=self.category,
            brand=self.brand,
            seller=self.user,
            regular_price=99.99
        )

    def test_review_creation(self):
        """Test creating a product review"""
        review = ProductReview.objects.create(
            product=self.product,
            user=self.user,
            rating=5,
            title='Great Product',
            comment='Really enjoyed this product'
        )
        self.assertEqual(review.rating, 5)
        self.assertEqual(review.product, self.product)

    def test_review_validation(self):
        """Test review rating validation"""
        with self.assertRaises(Exception):
            ProductReview.objects.create(
                product=self.product,
                user=self.user,
                rating=6,  # Invalid rating
                title='Test Review',
                comment='Test Comment'
            )

class MongoDBConnectionTest(TestCase):
    """Test MongoDB connection and basic operations"""
    
    def test_mongodb_connection(self):
        """Test that we can connect to MongoDB and perform basic operations"""
        try:
            # Try to create and save a category
            category = Category.objects.create(
                name='MongoDB Test Category',
                description='Testing MongoDB Connection'
            )
            
            # Try to retrieve it
            retrieved = Category.objects.get(id=category.id)
            self.assertEqual(retrieved.name, 'MongoDB Test Category')
            
            # Try to update it
            retrieved.name = 'Updated Name'
            retrieved.save()
            
            # Verify update
            updated = Category.objects.get(id=category.id)
            self.assertEqual(updated.name, 'Updated Name')
            
            # Try to delete it
            category.delete()
            
            # Verify deletion
            with self.assertRaises(Category.DoesNotExist):
                Category.objects.get(id=category.id)
                
        except Exception as e:
            self.fail(f"MongoDB connection test failed: {str(e)}")
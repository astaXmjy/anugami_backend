# categories/tests.py
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from .models import Category, CategoryImage, CategoryAttribute, CategorySEO
from .services import CategoryService

class CategoryModelTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            name='Test Category',
            description='Test Description'
        )
        self.child_category = Category.objects.create(
            name='Child Category',
            description='Child Description',
            parent=self.category
        )

    def test_category_creation(self):
        self.assertEqual(self.category.name, 'Test Category')
        self.assertTrue(self.category.slug)
        self.assertEqual(self.category.subcategory_count, 1)

    def test_category_tree(self):
        self.assertIsNone(self.category.parent)
        self.assertEqual(self.child_category.parent, self.category)
        self.assertEqual(list(self.category.children.all()), [self.child_category])

    def test_category_seo(self):
        seo = CategorySEO.objects.create(
            category=self.category,
            page_title='Test Title',
            meta_description='Test Meta Description'
        )
        self.assertEqual(seo.category, self.category)

class CategoryServiceTests(TestCase):
    def setUp(self):
        self.service = CategoryService()
        self.category = Category.objects.create(
            name='Test Category',
            description='Test Description'
        )

    def test_get_category(self):
        retrieved = self.service.get_category_by_id(self.category.id)
        self.assertEqual(retrieved, self.category)

    def test_create_category(self):
        data = {
            'name': 'New Category',
            'description': 'New Description'
        }
        new_category = self.service.create_category(data)
        self.assertEqual(new_category.name, 'New Category')
        self.assertTrue(new_category.slug)

    def test_move_category(self):
        parent = Category.objects.create(name='Parent')
        child = Category.objects.create(name='Child')
        self.service.move_category(child.id, parent.id, 'first-child')
        child.refresh_from_db()
        self.assertEqual(child.parent, parent)

class CategoryAPITests(APITestCase):
    def setUp(self):
        self.category = Category.objects.create(
            name='Test Category',
            description='Test Description'
        )
        self.list_url = reverse('categories:category-list')
        self.detail_url = reverse('categories:category-detail', 
                                kwargs={'slug': self.category.slug})

    def test_list_categories(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_create_category(self):
        data = {
            'name': 'New Category',
            'description': 'New Description'
        }
        response = self.client.post(self.list_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Category.objects.count(), 2)

    def test_update_category(self):
        data = {'name': 'Updated Category'}
        response = self.client.patch(self.detail_url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.category.refresh_from_db()
        self.assertEqual(self.category.name, 'Updated Category')

    def test_delete_category(self):
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Category.objects.count(), 0)

    def test_category_tree(self):
        url = reverse('categories:category-tree')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_move_category(self):
        parent = Category.objects.create(name='Parent')
        url = reverse('categories:category-move', kwargs={'slug': self.category.slug})
        data = {
            'target': str(parent.id),
            'position': 'first-child'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.category.refresh_from_db()
        self.assertEqual(self.category.parent, parent)

    def test_bulk_actions(self):
        url = reverse('categories:category-bulk-action')
        data = {
            'ids': [str(self.category.id)],
            'action': 'deactivate'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.category.refresh_from_db()
        self.assertFalse(self.category.is_active)
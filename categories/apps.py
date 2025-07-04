# categories/apps.py
from django.apps import AppConfig

class CategoriesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'categories'
    verbose_name = 'Category Management'

    def ready(self):
        import categories.signals  # Import signals if you have any
from django.apps import AppConfig

class ProductsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'products'
    verbose_name = 'Product Management'

    def ready(self):
        pass
        """Import signals and register database routers"""
        # try:
        #     import products.signals  # noqa
        # except ImportError:
        #     pass
import sys
from django.conf import settings

class DatabaseRouter:
    def __init__(self):
        # Core Django apps MUST use SQLite
        self.sqlite_apps = [
            'auth', 'contenttypes', 'sessions', 'admin',
            'system_users', 'django.contrib'
        ]

        self.mongodb_apps = [
            'products', 'categories', 'blogs', 'media', 
            'media_management', 'offers', 'promo_codes', 
            'chat', 'featured_sections', 'sliders', 'faq'
        ]

        self.firebase_apps = [
            'sellers', 'brands', 'notifications', 'orders', 
            'payments', 'support_tickets', 'reports', 
            'returns', 'customers'
        ]

    def db_for_read(self, model, **hints):
        # Always use default database during testing
        if 'test' in sys.argv:
            return 'default'

        app_label = model._meta.app_label

        # Prioritize SQLite for core apps
        if any(app in app_label for app in self.sqlite_apps):
            return 'default'
        
        if app_label in self.mongodb_apps:
            return 'mongodb'
        
        if app_label in self.firebase_apps:
            return 'firebase'
        
        # Default to SQLite
        return 'default'

    def db_for_write(self, model, **hints):
        return self.db_for_read(model, **hints)

    def allow_relation(self, obj1, obj2, **hints):
        # Always allow relations with default (SQLite) database
        return (
            obj1._state.db == obj2._state.db or 
            obj1._state.db == 'default' or 
            obj2._state.db == 'default'
        )

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        # Always migrate core apps to default (SQLite)
        if any(app in app_label for app in self.sqlite_apps):
            return db == 'default'
        
        if app_label in self.mongodb_apps:
            return db == 'mongodb'
        
        if app_label in self.firebase_apps:
            return db == 'firebase'
        
        # Default to SQLite
        return db == 'default'
from django.apps import AppConfig

class SystemUsersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "system_users"

    def ready(self):
        import system_users.signals  # Ensure signals are loaded

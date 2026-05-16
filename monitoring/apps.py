"""Django app configuration for the monitoring app."""

from django.apps import AppConfig


class MonitoringConfig(AppConfig):
    """Configuration for the monitoring (user action logging & dashboard) app."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'monitoring'

    def ready(self):
        """Import signal handlers so they are registered at startup."""
        import monitoring.signals  # noqa: F401

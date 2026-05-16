"""Django app configuration for the pages app."""

from django.apps import AppConfig


class PagesConfig(AppConfig):
    """Configuration for the pages (static/public pages) app."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'pages'

"""Django app configuration for the files app."""

from django.apps import AppConfig


class FilesConfig(AppConfig):
    """Configuration for the files (secure file storage) app."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'files'

"""Django app configuration for the Accounts app."""

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Configuration for the Accounts (authentication & user management) app."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Accounts'

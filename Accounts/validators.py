"""Custom password validators for the Accounts app.

These validators supplement Django's built-in password validation and the
``django_password_validators`` package configured in settings.
"""

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class NoSpecialCharacterValidator:
    """Reject passwords containing certain special characters.

    Allowed special characters: ``@``, ``#``, ``$``.
    All other special characters (e.g. ``%``, ``^``, ``*``, etc.) are rejected.
    """

    DISALLOWED = ['%', '^', '*', '(', ')', '!', '?', '<', '>', '{', '}', '[', ']', '|', '\\']

    def validate(self, password, user=None):
        """Raise ``ValidationError`` if *password* contains disallowed characters."""
        if any(char in password for char in self.DISALLOWED):
            raise ValidationError(
                _("The password should not contain special characters... except @, #, $"),
                code='no_special_characters',
            )

    def get_help_text(self):
        """Return a human-readable description of this validator."""
        return _("كلمة السر لا يجب أن تحتوي على علامات خاصة مثل @, #, $, إلخ.")


class MinimumLengthValidator:
    """Enforce a minimum password length of 10 characters."""

    def validate(self, password, user=None):
        """Raise ``ValidationError`` if *password* is shorter than 10 characters."""
        if len(password) < 10:
            raise ValidationError(
                _("This password is too short. It must contain at least 10 characters."),
                code='password_too_short',
            )

    def get_help_text(self):
        """Return a human-readable description of this validator."""
        return _("Your password must be at least 10 characters long.")

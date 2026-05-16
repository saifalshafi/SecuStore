"""Models for the monitoring app.

Provides ``UserActionLog`` which records user actions detected via Django
signals (login, logout, file upload/delete, etc.).
"""

from django.contrib.auth.models import User
from django.db import models


class UserActionLog(models.Model):
    """Log entry for a user action detected by a Django signal.

    Attributes:
        user: The user who performed the action (``None`` for anonymous).
        action: Human-readable description of the action.
        timestamp: When the action occurred.
        ip_address: Client IP address (if available).
        file_name: Name of the file involved (for file-related actions).
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    action = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    file_name = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        username = self.user.username if self.user else 'Anonymous'
        return f"{username} - {self.action} - {self.timestamp}"

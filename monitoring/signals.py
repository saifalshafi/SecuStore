"""Signal handlers for the monitoring app.

Listens to Django auth signals and model lifecycle signals to automatically
create ``UserActionLog`` entries for login, logout, failed login, file
upload, file deletion, and file download events.
"""

import logging

from django.contrib.auth.models import User
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from files.models import File
from .models import UserActionLog

logger = logging.getLogger(__name__)


def _get_client_ip(request):
    """Extract the client IP address from the request headers.

    Checks ``HTTP_X_FORWARDED_FOR`` first (for proxied requests), then
    falls back to ``REMOTE_ADDR``.
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    """Record a successful login event."""
    ip = _get_client_ip(request)
    UserActionLog.objects.create(user=user, action="Logged in", ip_address=ip)
    logger.info(f"User {user.username} logged in from IP {ip}.")


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    """Record a logout event."""
    ip = _get_client_ip(request)
    UserActionLog.objects.create(user=user, action="Logged out", ip_address=ip)
    logger.info(f"User {user.username} logged out from IP {ip}.")


@receiver(user_login_failed)
def log_user_login_failed(sender, credentials, **kwargs):
    """Record a failed login attempt."""
    username = credentials.get('username')
    UserActionLog.objects.create(
        user=None,
        action=f"Failed login attempt for username: {username}",
    )
    logger.warning(f"Failed login attempt for username: {username}")


@receiver(post_save, sender=File)
def log_file_upload(sender, instance, created, **kwargs):
    """Record a file upload event, flagging executable file attempts."""
    if created:
        file_name = instance.file_metadata.name
        if file_name.endswith('.exe'):
            UserActionLog.objects.create(
                user=instance.owner,
                action=f"Attempted to upload executable file '{file_name}'",
            )
            logger.warning(
                f"Executable file '{file_name}' upload attempt by {instance.owner.username}."
            )
        else:
            UserActionLog.objects.create(
                user=instance.owner,
                action=f"Uploaded file '{file_name}'",
            )
            logger.info(f"File '{file_name}' uploaded by {instance.owner.username}.")


@receiver(post_delete, sender=File)
def log_file_deletion(sender, instance, **kwargs):
    """Record a file deletion event."""
    file_name = instance.file_metadata.name
    UserActionLog.objects.create(
        user=instance.owner,
        action=f"Deleted file '{file_name}'",
    )
    logger.info(f"File '{file_name}' deleted by {instance.owner.username}.")


@receiver(post_save, sender=File)
def log_file_download(sender, instance, created, **kwargs):
    """Record a file download event (triggered by non-creation updates)."""
    if not created:
        file_name = instance.file_metadata.name
        UserActionLog.objects.create(
            user=instance.owner,
            action=f"Downloaded file '{file_name}'",
        )
        logger.info(f"File '{file_name}' downloaded by {instance.owner.username}.")

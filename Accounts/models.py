"""Models for the Accounts app."""

from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


class OTP(models.Model):
    """One-Time Password — stores only the SHA-256 hash, never plain text."""
    user_email = models.EmailField()
    otp_hash   = models.CharField(max_length=64)  # SHA-256 hex digest
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user_email} — {self.created_at}"


class Profile(models.Model):
    """User profile with profile image."""
    user  = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile'
    )
    image = models.ImageField(
        upload_to='profile_images/',
        default='profile_images/default.png',
        blank=True,
    )

    def __str__(self):
        return f"{self.user.username}'s Profile"


@receiver(post_save, sender=User)
def create_or_update_profile(sender, instance, created, **kwargs):
    """Auto-create a Profile when a new User is created."""
    Profile.objects.get_or_create(user=instance)


class KnownIP(models.Model):
    user       = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='known_ips'
    )
    ip_address = models.GenericIPAddressField()
    first_seen = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'ip_address')

    def __str__(self):
        return f"{self.user.username} — {self.ip_address}"


class SecureShareLink(models.Model):
    file       = models.ForeignKey(
        'files.File',
        on_delete=models.CASCADE,
        related_name='share_links'
    )
    token      = models.CharField(max_length=64, unique=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    expires_at = models.DateTimeField()
    used       = models.BooleanField(default=False)

    def is_valid(self):
        return not self.used and self.expires_at > timezone.now()

    def __str__(self):
        return f"ShareLink for {self.file}"
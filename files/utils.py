"""Utility functions for the files app."""

import hashlib
import hmac
import base64

from django.conf import settings

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

from .models import AuditLog

_HMAC_KEY = settings.SECRET_KEY.encode()


def _get_fernet():
    """Create a Fernet cipher from the master key in settings."""
    master = settings.MASTER_ENCRYPTION_KEY.encode()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b'secustore_salt_v1',
        iterations=100000,
        backend=default_backend(),
    )
    key = base64.urlsafe_b64encode(kdf.derive(master))
    return Fernet(key)


def encrypt_aes_key(raw_key):
    """Encrypt the raw AES key before storing in database.

    Args:
        raw_key: Raw 32-byte AES key.

    Returns:
        bytes: Encrypted AES key.
    """
    f = _get_fernet()
    return f.encrypt(raw_key)


def decrypt_aes_key(encrypted_key):
    """Decrypt the AES key retrieved from database.

    Args:
        encrypted_key: Encrypted AES key bytes.

    Returns:
        bytes: Raw 32-byte AES key.
    """
    if isinstance(encrypted_key, memoryview):
        encrypted_key = bytes(encrypted_key)
    if len(encrypted_key) == 32:
        return encrypted_key
    f = _get_fernet()
    return f.decrypt(encrypted_key)


def generate_hmac(data_bytes):
    """Generate an HMAC-SHA256 hex digest."""
    return hmac.new(_HMAC_KEY, data_bytes, hashlib.sha256).hexdigest()


def verify_hmac(data_bytes, signature):
    """Verify HMAC-SHA256 signature."""
    expected = generate_hmac(data_bytes)
    return hmac.compare_digest(expected, signature)


def log_event(request, action, details=""):
    """Create an AuditLog entry."""
    username = request.user.username if request.user.is_authenticated else 'Anonymous'
    full_details = f"{username}: {details}" if details else username

    AuditLog.objects.create(
        user=request.user if request.user.is_authenticated else None,
        action=action,
        ip_address=request.META.get('REMOTE_ADDR', ''),
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:255],
        details=full_details,
    )
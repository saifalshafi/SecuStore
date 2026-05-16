"""Utility functions for the Accounts app.

Security improvements:
- OTP generated with ``secrets`` (cryptographically secure CSPRNG).
- OTP stored as SHA-256 hash — plain text is never persisted to the DB.
"""

import hashlib
import hmac as _hmac
import secrets
import threading

from django.conf import settings
from django.core.mail import send_mail
from django.utils.timezone import now

from .models import OTP


def _hash_otp(plain_otp: str) -> str:
    """Return SHA-256 hex digest of the OTP. Only the hash is stored in DB."""
    return hashlib.sha256(plain_otp.encode()).hexdigest()


# ── OTP email templates per purpose ──────────────────────────────────────────
_OTP_TEMPLATES = {
    'login': {
        'subject': 'Your OTP Code — SecuStore',
        'intro':   'Your one-time verification code for logging in is:',
    },
    'signup': {
        'subject': 'Verify Your Email — SecuStore Account Creation',
        'intro':   'Thanks for signing up to SecuStore! Use the code below to verify your email and finish creating your account:',
    },
    'password_change': {
        'subject': '🔐 Password Change Verification — SecuStore',
        'intro':   'You requested to change your password. Use the code below to confirm this action:',
    },
}


def send_otp_to_email(user_email: str, purpose: str = 'login') -> None:
    """Generate a secure 6-digit OTP, store its hash, and email the plain code.

    ``purpose`` controls the email subject/body so the user knows why they got
    the code (login, signup, or password change).
    """
    plain_otp = f"{secrets.randbelow(900000) + 100000}"
    OTP.objects.create(
        user_email=user_email,
        otp_hash=_hash_otp(plain_otp),
        created_at=now(),
    )

    template = _OTP_TEMPLATES.get(purpose, _OTP_TEMPLATES['login'])
    subject  = template['subject']
    body = (
        f"{template['intro']}\n\n"
        f"    {plain_otp}\n\n"
        f"This code expires in 5 minutes.\n"
        f"If you did not request this, please ignore this email."
    )

    def _send():
        try:
            send_mail(
                subject,
                body,
                settings.EMAIL_HOST_USER,
                [user_email],
                fail_silently=True,
            )
        except Exception:
            pass

    threading.Thread(target=_send, daemon=True).start()


def verify_otp_code(user_email: str, entered_otp: str) -> bool:
    """Return True if entered_otp matches the stored hash (constant-time compare)."""
    entered_hash = _hash_otp(entered_otp)
    try:
        otp_record = OTP.objects.filter(user_email=user_email).latest('created_at')
        return _hmac.compare_digest(otp_record.otp_hash, entered_hash)
    except OTP.DoesNotExist:
        return False


def send_login_notification(user, request) -> None:
    """Send a login-alert email to the user in a background thread."""
    ip         = request.META.get('REMOTE_ADDR', 'Unknown')
    user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')[:100]
    login_time = now().strftime('%Y-%m-%d %H:%M:%S UTC')

    body = (
        f'Hello {user.username},\n\n'
        f'A new login was detected on your account:\n\n'
        f'  Time   : {login_time}\n'
        f'  IP     : {ip}\n'
        f'  Device : {user_agent}\n\n'
        f'If this was NOT you, change your password immediately!'
    )

    def _send():
        try:
            send_mail(
                '🔔 New Login to Your SecuStore Account',
                body, settings.EMAIL_HOST_USER, [user.email], fail_silently=True,
            )
        except Exception:
            pass

    threading.Thread(target=_send, daemon=True).start()

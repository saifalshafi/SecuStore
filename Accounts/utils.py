"""
Utility functions for the Accounts app.

Security improvements:
- OTP generated with secrets (cryptographically secure CSPRNG).
- OTP stored as SHA-256 hash — plain text is never persisted to the DB.
"""

import hashlib
import hmac
import secrets

from django.conf import settings
from django.core.mail import send_mail
from django.utils.timezone import now

from .models import OTP


# ── OTP Hashing ──────────────────────────────────────────

def _hash_otp(plain_otp: str) -> str:
    """Return SHA-256 hex digest of the OTP."""
    return hashlib.sha256(plain_otp.encode()).hexdigest()


# ── Email Templates ───────────────────────────────────────

_OTP_TEMPLATES = {
    'login': {
        'subject': 'Your OTP Code — SecuStore',
        'intro': 'Your one-time verification code for logging in is:',
    },
    'signup': {
        'subject': 'Verify Your Email — SecuStore',
        'intro': 'Use this code to verify your email and complete signup:',
    },
    'password_change': {
        'subject': 'Password Change Verification — SecuStore',
        'intro': 'Use this code to confirm your password change:',
    },
}


# ── SEND OTP ─────────────────────────────────────────────

def send_otp_to_email(user_email: str, purpose: str = 'login') -> None:
    """
    Generate OTP, store hash, and send email (SYNCHRONOUS for debugging).
    """

    plain_otp = str(secrets.randbelow(900000) + 100000)

    # Save hashed OTP in DB
    OTP.objects.create(
        user_email=user_email,
        otp_hash=_hash_otp(plain_otp),
        created_at=now(),
    )

    template = _OTP_TEMPLATES.get(purpose, _OTP_TEMPLATES['login'])

    subject = template['subject']
    body = (
        f"{template['intro']}\n\n"
        f"{plain_otp}\n\n"
        f"This code expires in 5 minutes.\n"
        f"If you did not request this, ignore this email."
    )

    print("📧 OTP EMAIL SENDING...")
    print("To:", user_email)
    print("OTP:", plain_otp)

    # 🔥 IMPORTANT: fail_silently=False so you SEE errors
    send_mail(
        subject,
        body,
        settings.EMAIL_HOST_USER,
        [user_email],
        fail_silently=False,
    )

    print("📧 EMAIL SENT FUNCTION FINISHED")


# ── VERIFY OTP ───────────────────────────────────────────

def verify_otp_code(user_email: str, entered_otp: str) -> bool:
    """Check OTP using constant-time comparison."""

    entered_hash = _hash_otp(entered_otp)

    try:
        otp_record = OTP.objects.filter(user_email=user_email).latest('created_at')
        return hmac.compare_digest(otp_record.otp_hash, entered_hash)
    except OTP.DoesNotExist:
        return False


# ── LOGIN NOTIFICATION ────────────────────────────────────

def send_login_notification(user, request) -> None:
    """Send login alert email."""

    ip = request.META.get('REMOTE_ADDR', 'Unknown')
    user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')[:120]
    login_time = now().strftime('%Y-%m-%d %H:%M:%S')

    body = (
        f"Hello {user.username},\n\n"
        f"New login detected:\n\n"
        f"Time: {login_time}\n"
        f"IP: {ip}\n"
        f"Device: {user_agent}\n\n"
        f"If this wasn't you, change your password immediately."
    )

    send_mail(
        'New Login Alert — SecuStore',
        body,
        settings.EMAIL_HOST_USER,
        [user.email],
        fail_silently=False,
    )
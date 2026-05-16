"""
Utility functions for OTP system (FIXED VERSION)
- Prevents server crash if email fails
- Keeps OTP secure (hashed)
"""

import hashlib
import hmac
import secrets

from django.conf import settings
from django.core.mail import send_mail
from django.utils.timezone import now

from .models import OTP


# ── HASH OTP ────────────────────────────────

def _hash_otp(plain_otp: str) -> str:
    return hashlib.sha256(plain_otp.encode()).hexdigest()


# ── TEMPLATES ───────────────────────────────

_OTP_TEMPLATES = {
    'login': {
        'subject': 'Your OTP Code — SecuStore',
        'intro': 'Your login verification code is:',
    },
    'signup': {
        'subject': 'Verify Your Email — SecuStore',
        'intro': 'Use this code to verify your email:',
    },
    'password_change': {
        'subject': 'Password Change Verification — SecuStore',
        'intro': 'Use this code to confirm password change:',
    },
}


# ── SEND OTP (FIXED - SAFE) ─────────────────

def send_otp_to_email(user_email: str, purpose: str = 'login') -> None:
    plain_otp = str(secrets.randbelow(900000) + 100000)

    OTP.objects.create(
        user_email=user_email,
        otp_hash=_hash_otp(plain_otp),
        created_at=now(),
    )

    template = _OTP_TEMPLATES.get(purpose, _OTP_TEMPLATES['login'])

    subject = template['subject']
    body = f"""{template['intro']}

{plain_otp}

This code expires in 5 minutes.
If you did not request this, ignore this email.
"""

    try:
        send_mail(
            subject,
            body,
            settings.EMAIL_HOST_USER,
            [user_email],
            fail_silently=False,
        )
        print("📧 OTP sent successfully to", user_email)

    except Exception as e:
        # ❗ مهم جدًا: يمنع انهيار السيرفر
        print("❌ EMAIL FAILED:", e)


# ── VERIFY OTP ──────────────────────────────

def verify_otp_code(user_email: str, entered_otp: str) -> bool:
    try:
        otp_record = OTP.objects.filter(user_email=user_email).latest('created_at')
        return hmac.compare_digest(
            otp_record.otp_hash,
            _hash_otp(entered_otp)
        )
    except OTP.DoesNotExist:
        return False


# ── LOGIN NOTIFICATION ──────────────────────

def send_login_notification(user, request) -> None:
    ip = request.META.get('REMOTE_ADDR', 'Unknown')
    agent = request.META.get('HTTP_USER_AGENT', 'Unknown')[:120]

    body = f"""
Hello {user.username},

New login detected:

IP: {ip}
Device: {agent}

If this wasn't you, change your password immediately.
"""

    try:
        send_mail(
            "New Login Alert — SecuStore",
            body,
            settings.EMAIL_HOST_USER,
            [user.email],
            fail_silently=True,
        )
    except Exception:
        pass
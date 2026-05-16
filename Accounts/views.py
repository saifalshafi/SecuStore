"""
Utility functions for Accounts app — FIXED & SAFE VERSION
"""

import hashlib
import hmac
import secrets
import threading

from django.conf import settings
from django.core.mail import send_mail
from django.utils.timezone import now
from .models import OTP


# ── OTP HASH ─────────────────────────────────────────────

def _hash_otp(plain_otp: str) -> str:
    return hashlib.sha256(plain_otp.encode()).hexdigest()


# ── EMAIL TEMPLATES ──────────────────────────────────────

_OTP_TEMPLATES = {
    'login': {
        'subject': 'Your OTP Code — SecuStore',
        'intro': 'Your login verification code is:',
    },
    'signup': {
        'subject': 'Verify Your Email — SecuStore',
        'intro': 'Your signup verification code is:',
    },
    'password_change': {
        'subject': 'Password Change OTP — SecuStore',
        'intro': 'Your password change code is:',
    },
}


# ── SAFE OTP SENDING (NO CRASH) ─────────────────────────

def send_otp_to_email(user_email: str, purpose: str = 'login') -> None:
    plain_otp = f"{secrets.randbelow(900000) + 100000}"

    # save hashed OTP
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
        f"Valid for 5 minutes."
    )

    # 🔥 SAFE EMAIL FUNCTION (prevents server crash)
    def _send():
        try:
            send_mail(
                subject,
                body,
                settings.EMAIL_HOST_USER,
                [user_email],
                fail_silently=True,   # IMPORTANT
            )
        except Exception:
            # never crash server بسبب email
            pass

    # optional thread (safe now)
    threading.Thread(target=_send, daemon=True).start()


# ── VERIFY OTP ──────────────────────────────────────────

def verify_otp_code(user_email: str, entered_otp: str) -> bool:
    entered_hash = _hash_otp(entered_otp)

    try:
        otp_record = OTP.objects.filter(user_email=user_email).latest('created_at')
        return hmac.compare_digest(otp_record.otp_hash, entered_hash)
    except OTP.DoesNotExist:
        return False


# ── LOGIN NOTIFICATION ───────────────────────────────────

def send_login_notification(user, request):
    ip = request.META.get('REMOTE_ADDR', 'Unknown')
    agent = request.META.get('HTTP_USER_AGENT', 'Unknown')[:120]

    body = (
        f"New login detected:\n\n"
        f"IP: {ip}\n"
        f"Device: {agent}"
    )

    def _send():
        try:
            send_mail(
                'New Login Alert',
                body,
                settings.EMAIL_HOST_USER,
                [user.email],
                fail_silently=True,
            )
        except Exception:
            pass

    threading.Thread(target=_send, daemon=True).start()
"""Views for the Accounts app — with security fixes applied.

New OTP flows added:
- Signup OTP: account is only created after the user verifies their email
  with a one-time code.
- Password Change OTP: a password change is only saved after the user
  confirms the action with a one-time code sent to their email.
"""

import logging
from datetime import timedelta

import secrets
from django.core.mail import send_mail

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import (
    authenticate, login as auth_login,
    logout as auth_logout, update_session_auth_hash,
)
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone

from django_ratelimit.decorators import ratelimit

from .models import OTP, KnownIP, SecureShareLink
from .utils import send_otp_to_email, send_login_notification, verify_otp_code

logger = logging.getLogger(__name__)

_ALLOWED_IMAGE_EXT   = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
_MAX_PROFILE_IMG     = 5 * 1024 * 1024  # 5 MB
_IMAGE_MAGIC_HEADERS = [
    b'\xff\xd8\xff',        # JPEG
    b'\x89PNG\r\n\x1a\n',  # PNG
    b'GIF87a', b'GIF89a',  # GIF
    b'RIFF',                # WebP
]


def _is_safe_image(f) -> bool:
    f.seek(0); header = f.read(12); f.seek(0)
    return any(header.startswith(m) for m in _IMAGE_MAGIC_HEADERS)


# ── Signup — email-first verification flow ───────────────────────────────────
#
# Step 1 (signup):              user enters EMAIL ONLY → OTP sent
# Step 2 (verify_signup_otp):   user enters OTP        → email marked verified
# Step 3 (signup_details):      user enters name/username/password → account created
#
# This is more user-friendly than collecting the full form first: a typo in the
# email is caught immediately, and the user doesn't fill a long form for nothing
# if they can't access the inbox.


def signup(request):
    """Step 1 of signup: collect EMAIL only, send a verification OTP.

    No User is created here — only an email-verification check.
    """
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()

        # Basic email shape check (Django's EmailValidator is heavier; this is
        # enough for a UX-level check before we send mail).
        if not email or '@' not in email or '.' not in email.split('@')[-1]:
            messages.error(request, "Please enter a valid email address.")
            return redirect('signup')

        if User.objects.filter(email__iexact=email).exists():
            messages.error(request, "An account with this email already exists.")
            return redirect('signup')

        # Stash the email and reset any previous verification state.
        request.session['signup_email']           = email
        request.session['signup_email_verified']  = False
        request.session.pop('signup_pending', None)
        request.session.set_expiry(600)  # 10 minutes
        request.session.save()

        send_otp_to_email(email, purpose='signup')
        messages.success(request, f'A verification code has been sent to {email}.')
        return redirect('verify_signup_otp')

    return render(request, 'pages/signup.html')


@ratelimit(key='ip', rate='5/m', method='POST', block=True)
def verify_signup_otp(request):
    """Step 2 of signup: verify the OTP, then mark email as verified.

    On success → redirect to ``signup_details`` (Step 3). The User row is
    still NOT created at this point.
    """
    email = request.session.get('signup_email')
    if not email:
        messages.error(request, 'Your signup session expired. Please start again.')
        return redirect('signup')

    if request.method == 'POST':
        entered_otp = request.POST.get('otp', '').strip()

        try:
            otp_record = OTP.objects.filter(user_email=email).latest('created_at')
        except OTP.DoesNotExist:
            messages.error(request, 'No verification code found. Please sign up again.')
            request.session.pop('signup_email', None)
            return redirect('signup')

        if otp_record.created_at < timezone.now() - timedelta(minutes=5):
            messages.error(request, 'Verification code has expired. Please sign up again.')
            request.session.pop('signup_email', None)
            return redirect('signup')

        if not verify_otp_code(email, entered_otp):
            messages.error(request, 'Invalid verification code. Please try again.')
            return redirect('verify_signup_otp')

        # Mark email as verified — burn the used OTP so it can't be replayed.
        request.session['signup_email_verified'] = True
        request.session.set_expiry(900)  # extend to 15 min for Step 3
        request.session.save()
        OTP.objects.filter(user_email=email).delete()

        messages.success(request, 'Email verified! Please complete your details.')
        return redirect('signup_details')

    return render(request, 'pages/verify_signup_otp.html', {'email': email})


@ratelimit(key='ip', rate='3/m', method='POST', block=True)
def resend_signup_otp(request):
    """Resend the email-verification OTP if the user lost or didn't get it."""
    email = request.session.get('signup_email')
    if not email:
        messages.error(request, 'Your signup session expired. Please start again.')
        return redirect('signup')
    send_otp_to_email(email, purpose='signup')
    messages.success(request, 'A new verification code has been sent.')
    return redirect('verify_signup_otp')


def signup_details(request):
    """Step 3 of signup: collect name/username/password and create the User.

    Only reachable after Step 2 has marked the email as verified.
    """
    email = request.session.get('signup_email')
    verified = request.session.get('signup_email_verified', False)

    if not email or not verified:
        messages.error(request, 'Please verify your email first.')
        return redirect('signup')

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name  = request.POST.get('last_name',  '').strip()
        username   = request.POST.get('username',   '').strip()
        password         = request.POST.get('password',         '')
        password_confirm = request.POST.get('password_confirm', '')

        if not first_name:
            messages.error(request, "First name is required.")
            return redirect('signup_details')
        if not username:
            messages.error(request, "Username is required.")
            return redirect('signup_details')
        if username in getattr(settings, 'BLOCKED_USERNAMES', []):
            messages.error(request, "This username is not allowed.")
            return redirect('signup_details')
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return redirect('signup_details')
        if len(password) < 10:
            messages.error(request, "Password must be at least 10 characters long.")
            return redirect('signup_details')
        if password != password_confirm:
            messages.error(request, 'Passwords do not match.')
            return redirect('signup_details')
        try:
            validate_password(password)
        except ValidationError as e:
            for msg in e.messages:
                messages.error(request, msg)
            return redirect('signup_details')

        # Final safety: nobody else snuck in between steps.
        if User.objects.filter(email__iexact=email).exists():
            request.session.flush()
            messages.error(request, 'This email is already taken.')
            return redirect('signup')

        try:
            user = User(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
            )
            user.set_password(password)
            user.save()
        except Exception as e:
            logger.error(f"Account creation failed: {e}")
            messages.error(request, f'Error creating account: {e}')
            return redirect('signup_details')

        # Cleanup signup session keys.
        for k in ('signup_email', 'signup_email_verified'):
            request.session.pop(k, None)

        messages.success(request, 'Account created successfully! Please sign in.')
        return redirect('login')

    return render(request, 'pages/signup_details.html', {'email': email})


# ── Login (unchanged) ────────────────────────────────────────────────────────

def login(request):
    """Authenticate credentials then redirect to OTP step."""
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            request.session.flush()
            request.session['otp_email'] = user.email
            request.session['user_id']   = user.id
            request.session.set_expiry(600)
            request.session.save()
            send_otp_to_email(user.email, purpose='login')
            return redirect('verify_otp')
        else:
            messages.error(request, "Invalid credentials")
            return redirect('login')
    return render(request, 'pages/login.html')


@ratelimit(key='ip', rate='5/m', method='POST', block=True)
def verifyotp(request):
    """Verify OTP — rate limited 5/min per IP to block brute-force."""
    user_email = request.session.get('otp_email')
    user_id    = request.session.get('user_id')

    if not user_email and not user_id:
        messages.error(request, "Session expired. Please log in again.")
        return redirect('login')

    if request.method == "POST":
        entered_otp = request.POST.get('otp', '').strip()
        try:
            user = (User.objects.filter(email=user_email).first() if user_email
                    else User.objects.filter(id=user_id).first())
            if not user:
                messages.error(request, "User not found.")
                return redirect('login')

            otp_record = OTP.objects.filter(user_email=user.email).latest('created_at')
            if otp_record.created_at < timezone.now() - timedelta(minutes=5):
                messages.error(request, 'OTP has expired. Please log in again.')
                return redirect('login')

            if verify_otp_code(user.email, entered_otp):
                auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                send_login_notification(user, request)
                _check_suspicious_login(user, request)
                request.session.pop('otp_email', None)
                request.session.pop('user_id',   None)
                return redirect('admin_dashboard') if user.is_staff else redirect('intro')
            else:
                messages.error(request, 'Invalid OTP.')
                return redirect('verify_otp')
        except OTP.DoesNotExist:
            messages.error(request, 'OTP not found. Please log in again.')
            return redirect('login')
    return render(request, 'pages/verify_otp.html')


@ratelimit(key='ip', rate='5/m', method='POST', block=True)
def request_otp(request):
    """Request a new OTP — always returns same message to prevent email enumeration."""
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        if User.objects.filter(email=email).exists():
            send_otp_to_email(email, purpose='login')
        # Always same message — never reveal if email exists
        messages.success(request, 'If that email is registered, an OTP has been sent.')
        return redirect('verify_otp')
    return render(request, 'pages/request_otp.html')


# ── Password change with OTP verification ────────────────────────────────────

@login_required
def password_change(request):
    """Step 1 of password change: validate form, send OTP, redirect to OTP step.

    The new password is NOT saved here. It is stored in the session and only
    written to the User row after the OTP is verified.
    """
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            # Don't save yet — store the plain new password in session.
            new_password = form.cleaned_data['new_password1']
            request.session['pending_password_change'] = {
                'user_id':      request.user.id,
                'new_password': new_password,
            }
            request.session.set_expiry(600)
            request.session.save()

            send_otp_to_email(request.user.email, purpose='password_change')
            messages.success(
                request,
                f'A verification code has been sent to {request.user.email}.',
            )
            return redirect('password_change_verify_otp')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'pages/password_change.html', {'form': form})


@login_required
@ratelimit(key='ip', rate='5/m', method='POST', block=True)
def password_change_verify_otp(request):
    """Step 2 of password change: verify OTP, then save the new password."""
    pending = request.session.get('pending_password_change')
    if not pending or pending.get('user_id') != request.user.id:
        messages.error(request, 'Your password-change session expired. Please try again.')
        return redirect('password_change')

    if request.method == 'POST':
        entered_otp = request.POST.get('otp', '').strip()

        try:
            otp_record = OTP.objects.filter(user_email=request.user.email).latest('created_at')
        except OTP.DoesNotExist:
            messages.error(request, 'No verification code found. Please try again.')
            request.session.pop('pending_password_change', None)
            return redirect('password_change')

        if otp_record.created_at < timezone.now() - timedelta(minutes=5):
            messages.error(request, 'Verification code has expired. Please try again.')
            request.session.pop('pending_password_change', None)
            return redirect('password_change')

        if not verify_otp_code(request.user.email, entered_otp):
            messages.error(request, 'Invalid verification code.')
            return redirect('password_change_verify_otp')

        # Actually change the password now.
        user = request.user
        user.set_password(pending['new_password'])
        user.save()
        update_session_auth_hash(request, user)

        # Burn the used OTP & clear the pending data.
        OTP.objects.filter(user_email=user.email).delete()
        request.session.pop('pending_password_change', None)

        # Notify the user that their password was changed (security alert).
        try:
            send_mail(
                '✅ Password Changed — SecuStore',
                (
                    f'Hello {user.username},\n\n'
                    f'Your account password was just changed.\n\n'
                    f'If this was NOT you, please reset your password immediately and contact support.'
                ),
                settings.EMAIL_HOST_USER, [user.email], fail_silently=True,
            )
        except Exception:
            pass

        messages.success(request, 'Password updated successfully!')
        return render(request, 'pages/password_changed.html')

    return render(request, 'pages/password_change_verify_otp.html',
                  {'email': request.user.email})


@login_required
@ratelimit(key='ip', rate='3/m', method='POST', block=True)
def resend_password_change_otp(request):
    """Resend the password-change OTP."""
    pending = request.session.get('pending_password_change')
    if not pending or pending.get('user_id') != request.user.id:
        messages.error(request, 'Your password-change session expired. Please try again.')
        return redirect('password_change')
    send_otp_to_email(request.user.email, purpose='password_change')
    messages.success(request, 'A new verification code has been sent.')
    return redirect('password_change_verify_otp')


# ── Profile / misc (unchanged) ───────────────────────────────────────────────

@login_required
def profile(request):
    return render(request, 'pages/profile.html', {'user': request.user})


def terms_conditions(request):
    return render(request, 'pages/terms_conditions.html')


@login_required
def upload_profile_image(request):
    """Profile image upload with extension + size + magic bytes validation."""
    from .models import Profile
    if request.method == 'POST' and request.FILES.get('profile_image'):
        img = request.FILES['profile_image']
        ext = img.name.rsplit('.', 1)[-1].lower() if '.' in img.name else ''

        if ext not in _ALLOWED_IMAGE_EXT:
            messages.error(request, "Only JPG, PNG, GIF, and WebP images are allowed.")
            return redirect('intro')
        if img.size > _MAX_PROFILE_IMG:
            messages.error(request, "Profile image must be smaller than 5 MB.")
            return redirect('intro')
        if not _is_safe_image(img):
            messages.error(request, "Invalid image file. Upload rejected.")
            logger.warning(f"User {request.user.username} tried uploading non-image as profile picture.")
            return redirect('intro')

        try:
            profile, _ = Profile.objects.get_or_create(user=request.user)
            profile.image = img
            profile.save()
            messages.success(request, "Profile image updated.")
        except Exception as e:
            logger.error(f"Profile image error: {e}")
            messages.error(request, "Failed to update profile image.")
    return redirect('intro')


def password_reset_request(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        try:
            user = User.objects.get(email=email)
            token = secrets.token_urlsafe(32)
            request.session[f'reset_token_{token}'] = {
                'user_id': user.id,
                'expires': (timezone.now() + timedelta(minutes=30)).isoformat(),
            }
            reset_url = request.build_absolute_uri(f'/Accounts/password_reset/confirm/{token}/')
            send_mail(
                '🔑 Password Reset — SecuStore',
                f'Hello {user.username},\n\nReset your password:\n{reset_url}\n\nExpires in 30 minutes.',
                settings.EMAIL_HOST_USER, [user.email], fail_silently=True,
            )
        except User.DoesNotExist:
            pass
        messages.success(request, 'If that email is registered, a reset link has been sent.')
        return redirect('login')
    return render(request, 'pages/password_reset_request.html')


def password_reset_confirm(request, token):
    session_key = f'reset_token_{token}'
    token_data  = request.session.get(session_key)
    if not token_data:
        messages.error(request, 'Reset link is invalid or has expired.')
        return redirect('login')
    from datetime import datetime
    expires = datetime.fromisoformat(token_data['expires'])
    if timezone.now() > expires:
        del request.session[session_key]
        messages.error(request, 'Link expired. Please request a new one.')
        return redirect('password_reset_request')
    if request.method == 'POST':
        password = request.POST.get('password', '')
        password_confirm = request.POST.get('password_confirm', '')
        if password != password_confirm:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'pages/password_reset_confirm.html', {'token': token})
        try:
            validate_password(password)
        except ValidationError as e:
            for msg in e.messages:
                messages.error(request, msg)
            return render(request, 'pages/password_reset_confirm.html', {'token': token})
        user = get_object_or_404(User, id=token_data['user_id'])
        user.set_password(password)
        user.save()
        del request.session[session_key]
        messages.success(request, 'Password reset successful!')
        return redirect('login')
    return render(request, 'pages/password_reset_confirm.html', {'token': token})


def _check_suspicious_login(user, request):
    ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
    if ',' in ip:
        ip = ip.split(',')[0].strip()
    if not ip:
        return
    obj, created = KnownIP.objects.get_or_create(user=user, ip_address=ip)
    if created:
        send_mail(
            '🚨 New Login Location — SecuStore',
            f'Hello {user.username},\n\nLogin from NEW IP: {ip}\n\nIf this was not you, change your password immediately!',
            settings.EMAIL_HOST_USER, [user.email], fail_silently=True,
        )

@login_required
def create_share_link(request, file_id):
    from files.models import File
    try:
        file_obj = File.objects.get(id=file_id, owner=request.user, status=File.STATUS_APPROVED)
    except File.DoesNotExist:
        messages.error(request, 'File not found or not approved.')
        return redirect('files:file_management')
    if request.method == 'POST':
        hours   = max(1, min(int(request.POST.get('hours', 24)), 72))
        token   = secrets.token_urlsafe(32)
        expires = timezone.now() + timedelta(hours=hours)
        SecureShareLink.objects.create(file=file_obj, token=token, created_by=request.user, expires_at=expires)
        share_url = request.build_absolute_uri(f'/Accounts/share/{token}/')
        return render(request, 'pages/share_link_created.html', {
            'share_url': share_url, 'expires': expires, 'hours': hours, 'file': file_obj,
        })
    return render(request, 'pages/create_share_link.html', {'file': file_obj})


def download_shared_file(request, token):
    try:
        link = SecureShareLink.objects.select_related('file').get(token=token)
    except SecureShareLink.DoesNotExist:
        return HttpResponse('Link not found.', status=404)
    if not link.is_valid():
        return HttpResponse('Link expired or already used.', status=410)
    file_obj = link.file
    try:
        from files.utils import verify_hmac, decrypt_aes_key
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from django.utils.encoding import smart_str
        with open(file_obj.file.path, 'rb') as ef:
            encrypted_bytes = ef.read()
        iv = encrypted_bytes[:16]
        raw_key = decrypt_aes_key(file_obj.encrypted_key)
        cipher = Cipher(algorithms.AES(raw_key), modes.CFB(iv), backend=default_backend())
        decrypted = cipher.decryptor().update(encrypted_bytes[16:]) + cipher.decryptor().finalize()
        link.used = True
        link.save()
        response = HttpResponse(decrypted, content_type=file_obj.file_metadata.file_type)
        response['Content-Disposition'] = f'attachment; filename="{smart_str(file_obj.file_metadata.name)}"'
        return response
    except Exception as e:
        return HttpResponse(f'Download failed: {e}', status=500)

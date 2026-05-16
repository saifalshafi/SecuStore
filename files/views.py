"""Views for the files app — security hardened + User Quota."""

import logging
import os
import tempfile
import uuid

import clamd

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum
from django.http import HttpResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.utils.encoding import smart_str

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from django_ratelimit.decorators import ratelimit

from .blockchain import add_block, verify_chain
from .encryption import encrypt_file_storage
from .forms import FileMetadataForm
from .models import File, FileMetadata
from .utils import generate_hmac, verify_hmac, log_event, encrypt_aes_key, decrypt_aes_key

logger = logging.getLogger(__name__)

_BLOCKED_EXTENSIONS = {
    'exe','bat','sh','dll','js','php','py',
    'cmd','vbs','ps1','msi','scr','com','pif',
}
_MAX_UPLOAD_BYTES = 50 * 1024 * 1024

_DANGEROUS_MAGIC = [
    b'MZ', b'\x7fELF', b'#!/',
    b'\xca\xfe\xba\xbe', b'\xfe\xed\xfa\xce',
    b'\xfe\xed\xfa\xcf', b'\xce\xfa\xed\xfe', b'\xcf\xfa\xed\xfe',
]


def _check_magic_bytes(uploaded_file):
    uploaded_file.seek(0)
    header = uploaded_file.read(8)
    uploaded_file.seek(0)
    for magic in _DANGEROUS_MAGIC:
        if header.startswith(magic):
            return False, f"Dangerous signature: {header[:4].hex()}"
    return True, ''


def _check_user_quota(user, new_file_size: int) -> tuple[bool, str]:
    """Return (True, '') if user is within quota, (False, msg) if exceeded."""
    quota = getattr(settings, 'USER_STORAGE_QUOTA_BYTES', 0)
    if quota == 0:
        return True, ''
    used = FileMetadata.objects.filter(uploaded_by=user).aggregate(
        total=Sum('size')
    )['total'] or 0
    if used + new_file_size > quota:
        quota_mb = quota // (1024 * 1024)
        used_mb  = used  // (1024 * 1024)
        return False, f"Storage quota exceeded. Used: {used_mb}MB / {quota_mb}MB"
    return True, ''


def scan_uploaded_file(uploaded_file) -> bool:
    try:
        cd = clamd.ClamdNetworkSocket(host='127.0.0.1', port=3310, timeout=100)
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            uploaded_file.seek(0)
            for chunk in uploaded_file.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name
        result = cd.scan(tmp_path)
        os.remove(tmp_path)
        if result is None:
            return True
        return list(result.values())[0][0] == 'OK'
    except Exception as e:
        logger.warning(f"ClamAV unavailable: {e}")
        if getattr(settings, 'CLAMAV_REQUIRED', False):
            return False
        return True


@ratelimit(key='user', rate='10/m', method='POST', block=True)
@login_required
def file_upload_view(request):
    if request.method == 'POST' and request.FILES.get('file'):
        uploaded_file = request.FILES['file']
        try:
            # 1. Extension check
            ext = uploaded_file.name.rsplit('.', 1)[-1].lower() if '.' in uploaded_file.name else ''
            if ext in _BLOCKED_EXTENSIONS:
                messages.error(request, f"File type '.{ext}' is not allowed.")
                return redirect('files:upload')

            # 2. Size check
            if uploaded_file.size > _MAX_UPLOAD_BYTES:
                messages.error(request, "File size exceeds 50 MB limit.")
                return redirect('files:upload')

            # 3. User quota check
            within_quota, quota_msg = _check_user_quota(request.user, uploaded_file.size)
            if not within_quota:
                messages.error(request, quota_msg)
                return redirect('files:upload')

            # 4. Magic bytes check
            safe, reason = _check_magic_bytes(uploaded_file)
            if not safe:
                messages.error(request, "File rejected: dangerous file type detected.")
                log_event(request, 'failed_access', f"Magic bytes blocked: {reason}")
                return redirect('files:upload')

            # 5. Antivirus scan
            if not scan_uploaded_file(uploaded_file):
                messages.error(request, "File failed the security scan and was rejected.")
                log_event(request, 'failed_access', f"AV rejected: '{uploaded_file.name}'")
                return redirect('files:upload')

            uploaded_file.seek(0)

            metadata = FileMetadata.objects.create(
                name=uploaded_file.name, size=uploaded_file.size,
                file_type=uploaded_file.content_type,
                description=request.POST.get('description', ''),
                tags=request.POST.get('tags', ''),
                category=request.POST.get('category', ''),
                permissions=request.POST.get('permissions', 'private'),
                expiration_date=request.POST.get('expiration_date') or None,
                uploaded_by=request.user,
            )

            temp_path = os.path.join(settings.MEDIA_ROOT, f"{uuid.uuid4()}_{uploaded_file.name}")
            with open(temp_path, 'wb+') as dst:
                for chunk in uploaded_file.chunks():
                    dst.write(chunk)

            encrypted_path, aes_key = encrypt_file_storage(temp_path)
            with open(encrypted_path, 'rb') as ef:
                encrypted_bytes = ef.read()

            signature  = generate_hmac(encrypted_bytes)
            final_name = f"encrypted_{uuid.uuid4()}.enc"

            # Auto-approve files at or below the configured size threshold;
            # larger files require admin review before they can be downloaded.
            auto_approve_limit = getattr(settings, 'AUTO_APPROVE_SIZE_BYTES', 0)
            if auto_approve_limit and uploaded_file.size <= auto_approve_limit:
                initial_status = File.STATUS_APPROVED
                approved_at    = timezone.now()
            else:
                initial_status = File.STATUS_PENDING
                approved_at    = None

            new_file = File.objects.create(
                file_metadata=metadata, owner=request.user,
                description=metadata.description, tags=metadata.tags,
                category=metadata.category, permissions=metadata.permissions,
                expiration_date=metadata.expiration_date,
                encrypted_key=encrypt_aes_key(aes_key),
                hmac_signature=signature,
                status=initial_status,
                reviewed_at=approved_at,
            )
            with open(encrypted_path, 'rb') as ef:
                new_file.file.save(final_name, ef)

            os.remove(temp_path)
            os.remove(encrypted_path)

            log_event(request, 'upload', f"Uploaded '{uploaded_file.name}' HMAC={signature}")
            add_block('upload', request.user.username, uploaded_file.name, signature)

            if initial_status == File.STATUS_APPROVED:
                limit_mb = auto_approve_limit // (1024 * 1024)
                messages.success(
                    request,
                    f"'{uploaded_file.name}' uploaded and approved automatically "
                    f"(under {limit_mb} MB). Ready to download.",
                )
            else:
                limit_mb = auto_approve_limit // (1024 * 1024) if auto_approve_limit else 0
                size_mb  = uploaded_file.size // (1024 * 1024)
                messages.success(
                    request,
                    f"'{uploaded_file.name}' uploaded successfully ({size_mb} MB). "
                    f"Files over {limit_mb} MB need admin review before download.",
                )
            return redirect('files:file_management')

        except Exception as e:
            logger.error(f"Upload failed: {e}")
            log_event(request, 'failed_access', f"Upload failed: {e}")
            return HttpResponse(f"Upload failed: {e}", status=500)

    return render(request, 'pages/home.html', {'user_files': File.objects.filter(owner=request.user)})


@ratelimit(key='user', rate='20/m', method='POST', block=True)
@login_required
def file_download_view(request, file_id):
    if request.method != 'POST':
        messages.error(request, "Invalid download request.")
        return redirect('files:file_management')

    try:
        file_obj = File.objects.get(id=file_id, owner=request.user)
    except File.DoesNotExist:
        log_event(request, 'failed_access', f"Invalid download id={file_id}")
        raise Http404("File not found")

    if file_obj.status == File.STATUS_PENDING:
        messages.warning(request, "This file is pending admin review.")
        return redirect('files:file_management')
    if file_obj.status == File.STATUS_REJECTED:
        note = file_obj.rejection_note or "No reason given."
        messages.error(request, f"File rejected by admin. Reason: {note}")
        return redirect('files:file_management')

    try:
        with open(file_obj.file.path, 'rb') as ef:
            encrypted_bytes = ef.read()

        if not verify_hmac(encrypted_bytes, file_obj.hmac_signature):
            log_event(request, 'failed_access', f"HMAC mismatch: '{file_obj.file.name}'")
            return HttpResponse("Integrity check failed.", status=403)

        iv             = encrypted_bytes[:16]
        encrypted_data = encrypted_bytes[16:]
        raw_key        = decrypt_aes_key(file_obj.encrypted_key)
        cipher         = Cipher(algorithms.AES(raw_key), modes.CFB(iv), backend=default_backend())
        decrypted      = cipher.decryptor().update(encrypted_data) + cipher.decryptor().finalize()

        response = HttpResponse(decrypted, content_type=file_obj.file_metadata.file_type)
        response['Content-Disposition'] = f'attachment; filename="{smart_str(file_obj.file_metadata.name)}"'
        log_event(request, 'download', f"Downloaded '{file_obj.file.name}'")
        add_block('download', request.user.username, file_obj.file_metadata.name)
        return response

    except Exception as e:
        logger.error(f"Download error: {e}")
        return HttpResponse("Download failed.", status=500)


@login_required
def delete_file(request, file_id):
    try:
        file_obj = File.objects.get(id=file_id, owner=request.user)
    except File.DoesNotExist:
        return HttpResponse("File not found.", status=404)

    if request.method == 'POST':
        try:
            file_path = getattr(file_obj.file, "path", None)
            if file_obj.file and file_obj.file.name:
                file_obj.file.delete(save=False)
            file_obj.delete()
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
            log_event(request, 'delete', f"Deleted file id={file_id}")
            add_block('delete', request.user.username, f"file_id={file_id}")
            messages.success(request, "File deleted successfully.")
        except Exception as e:
            messages.error(request, "Error deleting file.")
    return redirect('files:file_management')


@login_required
def file_management_view(request):
    import random
    if random.randint(1, 50) == 1:
        try:
            from django.core.management import call_command
            call_command('delete_expired')
        except Exception:
            pass

    # Quota usage for display
    quota       = getattr(settings, 'USER_STORAGE_QUOTA_BYTES', 0)
    used_bytes  = FileMetadata.objects.filter(uploaded_by=request.user).aggregate(
        total=Sum('size')
    )['total'] or 0
    quota_pct   = int((used_bytes / quota) * 100) if quota else 0

    try:
        user_files = File.objects.filter(owner=request.user)
        return render(request, 'pages/file_management.html', {
            'user_files':  user_files,
            'used_bytes':  used_bytes,
            'quota_bytes': quota,
            'quota_pct':   quota_pct,
        })
    except Exception as e:
        return HttpResponse(f"Error: {e}", status=500)


@login_required
def home(request):
    return render(request, 'pages/home.html', {'user_files': File.objects.filter(owner=request.user)})


@login_required
def edit_metadata(request, file_id):
    try:
        file = File.objects.get(id=file_id, owner=request.user)
        if request.method == 'POST':
            old_expiration = file.file_metadata.expiration_date if file.file_metadata else None
            form = FileMetadataForm(request.POST, instance=file.file_metadata)
            if form.is_valid():
                metadata = form.save()

                # Keep File.expiration_date in sync with FileMetadata.expiration_date
                # so the delete_expired job uses the right value, and reset the
                # warning/auto-extension flags so the cycle starts fresh for the
                # new date.
                new_expiration = metadata.expiration_date
                fields_to_update = []
                if file.expiration_date != new_expiration:
                    file.expiration_date = new_expiration
                    fields_to_update.append('expiration_date')
                if old_expiration != new_expiration:
                    file.warning_email_sent = False
                    file.auto_extended      = False
                    file.warning_sent_at    = None
                    file.auto_extended_at   = None
                    fields_to_update.extend([
                        'warning_email_sent', 'auto_extended',
                        'warning_sent_at', 'auto_extended_at',
                    ])
                if fields_to_update:
                    file.save(update_fields=fields_to_update)

                messages.success(request, "Metadata updated.")
                return redirect('files:file_management')
        else:
            form = FileMetadataForm(instance=file.file_metadata)
        return render(request, 'edit_metadata.html', {'form': form, 'file': file})
    except File.DoesNotExist:
        return HttpResponse("File not found.", status=404)


# ── Admin views ──────────────────────────────────────────────────────────────

@staff_member_required
def admin_all_files_view(request):
    all_files = File.objects.select_related('owner', 'file_metadata').order_by('-uploaded_at')
    return render(request, 'pages/admin_all_files.html', {
        'all_files':      all_files,
        'pending_count':  all_files.filter(status=File.STATUS_PENDING).count(),
        'approved_count': all_files.filter(status=File.STATUS_APPROVED).count(),
        'rejected_count': all_files.filter(status=File.STATUS_REJECTED).count(),
    })


@staff_member_required
def admin_approve_file(request, file_id):
    file_obj = get_object_or_404(File, id=file_id)
    if request.method == 'POST':
        file_obj.status = File.STATUS_APPROVED
        file_obj.reviewed_by = request.user
        file_obj.reviewed_at = timezone.now()
        file_obj.rejection_note = ''
        file_obj.save()
        add_block('approve', request.user.username, str(file_obj))
        messages.success(request, f"File approved.")
    return redirect('files:admin_all_files')


@staff_member_required
def admin_reject_file(request, file_id):
    file_obj = get_object_or_404(File, id=file_id)
    if request.method == 'POST':
        note = request.POST.get('rejection_note', '').strip()
        file_obj.status = File.STATUS_REJECTED
        file_obj.reviewed_by = request.user
        file_obj.reviewed_at = timezone.now()
        file_obj.rejection_note = note
        file_obj.save()
        add_block('reject', request.user.username, str(file_obj), note)
        messages.warning(request, f"File rejected.")
    return redirect('files:admin_all_files')


@staff_member_required
def admin_download_file(request, file_id):
    file_obj = get_object_or_404(File, id=file_id)
    try:
        with open(file_obj.file.path, 'rb') as ef:
            encrypted_bytes = ef.read()
        if not verify_hmac(encrypted_bytes, file_obj.hmac_signature):
            return HttpResponse("Integrity check failed.", status=403)
        iv             = encrypted_bytes[:16]
        encrypted_data = encrypted_bytes[16:]
        raw_key        = decrypt_aes_key(file_obj.encrypted_key)
        cipher         = Cipher(algorithms.AES(raw_key), modes.CFB(iv), backend=default_backend())
        decrypted      = cipher.decryptor().update(encrypted_data) + cipher.decryptor().finalize()
        response = HttpResponse(decrypted, content_type=file_obj.file_metadata.file_type)
        response['Content-Disposition'] = f'attachment; filename="{smart_str(file_obj.file_metadata.name)}"'
        add_block('admin_download', request.user.username, file_obj.file_metadata.name)
        return response
    except Exception as e:
        return HttpResponse(f"Download failed: {e}", status=500)


@staff_member_required
def admin_delete_file(request, file_id):
    file_obj = get_object_or_404(File, id=file_id)
    if request.method == 'POST':
        name = str(file_obj)
        try:
            file_path = getattr(file_obj.file, "path", None)
            if file_obj.file and file_obj.file.name:
                file_obj.file.delete(save=False)
            file_obj.delete()
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
            add_block('admin_delete', request.user.username, name)
            messages.success(request, f"File deleted.")
        except Exception as e:
            messages.error(request, "Error deleting file.")
    return redirect('files:admin_all_files')


@staff_member_required
def admin_verify_blockchain(request):
    is_valid, message = verify_chain()
    return render(request, 'pages/admin_blockchain.html', {
        'is_valid': is_valid, 'message': message,
    })
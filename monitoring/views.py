"""Admin monitoring views."""

import csv
import logging
import os

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.db.models import Count, Sum
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect

from files.models import File, Block
from .models import UserActionLog

User = get_user_model()
logger = logging.getLogger(__name__)


@staff_member_required
def admin_dashboard_view(request):
    total_users  = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    staff_users  = User.objects.filter(is_staff=True).count()
    total_files  = File.objects.count()

    users_list = User.objects.annotate(
        file_count=Count('file'),
        total_size=Sum('file__file_metadata__size'),
    ).order_by('-date_joined')

    recent_blocks  = Block.objects.order_by('-index')[:20]
    recent_actions = UserActionLog.objects.order_by('-timestamp')[:15]

    return render(request, 'pages/dashboard.html', {
        'total_users':         total_users,
        'active_users':        active_users,
        'staff_users':         staff_users,
        'total_files':         total_files,
        'pending_files':       File.objects.filter(status=File.STATUS_PENDING).count(),
        'approved_files':      File.objects.filter(status=File.STATUS_APPROVED).count(),
        'rejected_files':      File.objects.filter(status=File.STATUS_REJECTED).count(),
        'users_list':          users_list,
        'recent_blocks':       recent_blocks,
        'recent_actions':      recent_actions,
        'user_upload_count':   UserActionLog.objects.filter(action__icontains="Uploaded").count(),
        'user_download_count': UserActionLog.objects.filter(action__icontains="Downloaded").count(),
        'user_delete_count':   UserActionLog.objects.filter(action__icontains="Deleted").count(),
        'user_login_count':    UserActionLog.objects.filter(action__icontains="Logged in").count(),
        'user_logout_count':   UserActionLog.objects.filter(action__icontains="Logged out").count(),
    })


@staff_member_required
def user_files_view(request, user_id):
    target_user = get_object_or_404(User, id=user_id)
    user_files  = File.objects.filter(owner=target_user).select_related('file_metadata')
    return render(request, 'pages/user_files.html', {
        'target_user': target_user, 'user_files': user_files,
    })


@staff_member_required
def admin_users_list(request):
    users = User.objects.annotate(
        file_count=Count('file'),
        total_size=Sum('file__file_metadata__size'),
    ).order_by('-date_joined')
    return render(request, 'pages/admin_users.html', {'users': users})


@staff_member_required
def admin_toggle_user(request, user_id):
    if request.method != 'POST':
        return redirect('admin_users_list')
    if request.user.id == user_id:
        messages.error(request, "You cannot deactivate your own account.")
        return redirect('admin_users_list')
    target = get_object_or_404(User, id=user_id)
    target.is_active = not target.is_active
    target.save()
    label = "activated" if target.is_active else "deactivated"
    UserActionLog.objects.create(
        user=request.user,
        action=f"Admin {label} account of '{target.username}'",
        ip_address=request.META.get('REMOTE_ADDR', ''),
    )
    messages.success(request, f"Account '{target.username}' {label}.")
    return redirect('admin_users_list')


@staff_member_required
def admin_delete_user(request, user_id):
    if request.method != 'POST':
        return redirect('admin_users_list')
    if request.user.id == user_id:
        messages.error(request, "You cannot delete your own account.")
        return redirect('admin_users_list')
    target   = get_object_or_404(User, id=user_id)
    username = target.username
    try:
        for f in File.objects.filter(owner=target):
            try:
                if f.file and os.path.exists(f.file.path):
                    os.remove(f.file.path)
            except Exception:
                pass
        target.delete()
        UserActionLog.objects.create(
            user=request.user,
            action=f"Admin deleted account '{username}'",
            ip_address=request.META.get('REMOTE_ADDR', ''),
        )
        messages.success(request, f"Account '{username}' deleted.")
    except Exception as e:
        messages.error(request, f"Failed to delete: {e}")
    return redirect('admin_users_list')


@staff_member_required
def admin_activity_log(request):
    logs = UserActionLog.objects.select_related('user').order_by('-timestamp')
    q_user   = request.GET.get('user',   '').strip()
    q_action = request.GET.get('action', '').strip()
    if q_user:   logs = logs.filter(user__username__icontains=q_user)
    if q_action: logs = logs.filter(action__icontains=q_action)
    return render(request, 'pages/admin_activity_log.html', {
        'logs': logs[:200], 'q_user': q_user, 'q_action': q_action,
    })


@staff_member_required
def export_activity_csv(request):
    """Export activity log as CSV."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="activity_report.csv"'
    writer = csv.writer(response)
    writer.writerow(['User', 'Action', 'Time', 'IP Address'])
    for log in UserActionLog.objects.select_related('user').order_by('-timestamp'):
        writer.writerow([
            log.user.username if log.user else 'Anonymous',
            log.action,
            log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            log.ip_address or '—',
        ])
    return response


@staff_member_required
def export_files_csv(request):
    """Export files report as CSV."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="files_report.csv"'
    writer = csv.writer(response)
    writer.writerow(['File Name', 'Owner', 'Size (bytes)', 'Type', 'Status', 'Uploaded', 'Reviewed By'])
    for f in File.objects.select_related('owner', 'file_metadata').order_by('-uploaded_at'):
        writer.writerow([
            f.file_metadata.name      if f.file_metadata else '—',
            f.owner.username,
            f.file_metadata.size      if f.file_metadata else 0,
            f.file_metadata.file_type if f.file_metadata else '—',
            f.status,
            f.uploaded_at.strftime('%Y-%m-%d %H:%M'),
            f.reviewed_by.username if f.reviewed_by else '—',
        ])
    return response

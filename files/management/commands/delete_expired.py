"""Management command — expiration lifecycle for stored files.

This command runs three jobs each time it's invoked:

  1. WARN   — Files whose expiration_date falls within ``WARNING_DAYS`` from
              today get an email to the owner, explaining the deletion policy
              and offering them a link to extend the expiration. The email
              also tells them that if they do nothing, the file's expiration
              will be auto-extended by ``AUTO_EXTENSION_DAYS`` days as a
              grace period before final deletion.

  2. EXTEND — Files whose expiration_date is already in the past *and* that
              have not yet been auto-extended get the auto-extension applied:
              expiration_date += AUTO_EXTENSION_DAYS, ``auto_extended=True``,
              and a notification email is sent.

  3. DELETE — Files whose expiration_date is in the past *and* that have
              already been auto-extended are finally deleted from storage,
              and the owner gets a deletion confirmation email.

Run periodically (cron / celery beat / scheduled task):

    python manage.py delete_expired

A randomized hook also calls it on a small percentage of page views
(see ``file_management_view``).
"""

from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.urls import reverse
from django.utils import timezone

from files.models import File


# Days before expiration when a warning email is sent.
WARNING_DAYS        = getattr(settings, 'EXPIRATION_WARNING_DAYS', 3)
# Length of the auto-extension grace period (days).
AUTO_EXTENSION_DAYS = getattr(settings, 'AUTO_EXTENSION_DAYS', 10)


def _site_url(path: str = '') -> str:
    """Return an absolute-ish URL for emails when no request is available."""
    base = getattr(settings, 'SITE_URL', '').rstrip('/')
    if base:
        return f'{base}{path}'
    return path  # caller can prepend their own host if needed


def _send(subject: str, body: str, to_email: str) -> None:
    """Send mail, swallowing errors so the command keeps running."""
    try:
        send_mail(
            subject, body, settings.EMAIL_HOST_USER, [to_email],
            fail_silently=True,
        )
    except Exception:
        pass


class Command(BaseCommand):
    help = (
        'Run the expiration lifecycle for stored files: send warning emails, '
        'auto-extend files past their expiration, and delete files past their '
        'extended expiration.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Report what would happen without making any changes.',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        today   = timezone.now().date()
        now_ts  = timezone.now()

        warned, extended, deleted = 0, 0, 0

        # ── 1. WARN ──────────────────────────────────────────────────────
        # Files expiring within the warning window that haven't been warned
        # yet, and that haven't already been auto-extended (no point warning
        # again after we've already given them the grace period).
        warn_window_end = today + timedelta(days=WARNING_DAYS)
        warn_qs = File.objects.filter(
            expiration_date__isnull=False,
            expiration_date__gte=today,
            expiration_date__lte=warn_window_end,
            warning_email_sent=False,
            auto_extended=False,
        ).select_related('owner', 'file_metadata')

        for f in warn_qs:
            try:
                self._send_warning_email(f)
                if not dry_run:
                    f.warning_email_sent = True
                    f.warning_sent_at    = now_ts
                    f.save(update_fields=['warning_email_sent', 'warning_sent_at'])
                warned += 1
            except Exception as e:
                self.stdout.write(f"[WARN]  failed for file {f.id}: {e}")

        # ── 2. EXTEND ────────────────────────────────────────────────────
        # Files whose expiration_date has passed but who haven't yet had
        # their auto-extension applied.
        extend_qs = File.objects.filter(
            expiration_date__isnull=False,
            expiration_date__lt=today,
            auto_extended=False,
        ).select_related('owner', 'file_metadata')

        for f in extend_qs:
            try:
                new_date = f.expiration_date + timedelta(days=AUTO_EXTENSION_DAYS)
                if not dry_run:
                    f.expiration_date = new_date
                    f.auto_extended    = True
                    f.auto_extended_at = now_ts
                    f.save(update_fields=[
                        'expiration_date', 'auto_extended', 'auto_extended_at',
                    ])
                    # Keep the metadata copy in sync.
                    if f.file_metadata:
                        f.file_metadata.expiration_date = new_date
                        f.file_metadata.save(update_fields=['expiration_date'])
                self._send_extension_email(f, new_date)
                extended += 1
            except Exception as e:
                self.stdout.write(f"[EXTEND] failed for file {f.id}: {e}")

        # ── 3. DELETE ────────────────────────────────────────────────────
        # Files past their expiration_date AND already auto-extended.
        delete_qs = File.objects.filter(
            expiration_date__isnull=False,
            expiration_date__lt=today,
            auto_extended=True,
        ).select_related('owner', 'file_metadata')

        for f in delete_qs:
            try:
                file_name = (
                    f.file_metadata.name if f.file_metadata
                    else (f.file.name if f.file else f'file_{f.id}')
                )
                owner_email = f.owner.email if f.owner else None
                if not dry_run:
                    if f.file:
                        try:
                            f.file.delete(save=False)
                        except Exception:
                            pass
                    f.delete()
                if owner_email:
                    self._send_deletion_email(f.owner.username, owner_email, file_name)
                deleted += 1
            except Exception as e:
                self.stdout.write(f"[DELETE] failed for file {f.id}: {e}")

        mode = ' (DRY RUN)' if dry_run else ''
        self.stdout.write(
            f"Expiration lifecycle complete{mode}: "
            f"{warned} warned, {extended} auto-extended, {deleted} deleted."
        )

    # ── Email helpers ────────────────────────────────────────────────────

    def _send_warning_email(self, f):
        owner = f.owner
        if not owner or not owner.email:
            return

        file_name = f.file_metadata.name if f.file_metadata else 'your file'
        days_left = (f.expiration_date - timezone.now().date()).days

        try:
            edit_path = reverse('files:edit_metadata', args=[f.id])
        except Exception:
            edit_path = f'/files/edit/{f.id}/'

        edit_link = _site_url(edit_path) or edit_path

        body = (
            f"Hello {owner.username},\n\n"
            f"This is a friendly reminder that your file is scheduled for deletion.\n\n"
            f"  File          : {file_name}\n"
            f"  Expires on    : {f.expiration_date.strftime('%Y-%m-%d')}"
            f"  ({days_left} day{'s' if days_left != 1 else ''} from now)\n\n"
            f"WHAT YOU CAN DO\n"
            f"  • Sign in to SecuStore and edit the file's expiration date to "
            f"keep it longer:\n"
            f"      {edit_link}\n\n"
            f"WHAT HAPPENS IF YOU DO NOTHING\n"
            f"  • On the expiration date, the site will automatically extend "
            f"your file by {AUTO_EXTENSION_DAYS} more days as a grace period.\n"
            f"  • After that grace period the file will be PERMANENTLY DELETED.\n\n"
            f"If you want to keep this file, please update the expiration date "
            f"before it's gone.\n\n"
            f"— SecuStore"
        )
        _send('⏰ Your file is about to expire — SecuStore', body, owner.email)

    def _send_extension_email(self, f, new_date):
        owner = f.owner
        if not owner or not owner.email:
            return
        file_name = f.file_metadata.name if f.file_metadata else 'your file'

        try:
            edit_path = reverse('files:edit_metadata', args=[f.id])
        except Exception:
            edit_path = f'/files/edit/{f.id}/'
        edit_link = _site_url(edit_path) or edit_path

        body = (
            f"Hello {owner.username},\n\n"
            f"Your file's expiration date had passed without action, so we "
            f"automatically extended it for {AUTO_EXTENSION_DAYS} more days "
            f"as a one-time grace period.\n\n"
            f"  File              : {file_name}\n"
            f"  New expiration    : {new_date.strftime('%Y-%m-%d')}\n\n"
            f"After that date the file will be PERMANENTLY DELETED — there "
            f"will be no further auto-extension.\n\n"
            f"If you want to keep this file, please sign in and update the "
            f"expiration date:\n"
            f"  {edit_link}\n\n"
            f"— SecuStore"
        )
        _send('🕒 Your file was auto-extended by '
              f'{AUTO_EXTENSION_DAYS} days — SecuStore', body, owner.email)

    def _send_deletion_email(self, username, owner_email, file_name):
        body = (
            f"Hello {username},\n\n"
            f"Your file '{file_name}' has been permanently deleted from "
            f"SecuStore because its expiration date (including the "
            f"{AUTO_EXTENSION_DAYS}-day grace period) has passed.\n\n"
            f"This action cannot be undone.\n\n"
            f"— SecuStore"
        )
        _send('🗑️ Your file has been deleted — SecuStore', body, owner_email)

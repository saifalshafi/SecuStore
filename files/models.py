"""Models for the files app."""
from django.contrib.auth.models import User
from django.db import models


class UserKey(models.Model):
    user           = models.OneToOneField(User, on_delete=models.CASCADE, related_name='keys')
    public_key     = models.TextField()
    private_key    = models.TextField()
    dh_private_key = models.BinaryField(null=True, blank=True)
    dh_public_key  = models.BinaryField(null=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Keys for {self.user.username}"


class FileMetadata(models.Model):
    name            = models.CharField(max_length=255)
    size            = models.PositiveIntegerField()
    file_type       = models.CharField(max_length=255)
    file_url        = models.CharField(max_length=255)
    description     = models.TextField()
    tags            = models.TextField(null=True, blank=True)
    category        = models.CharField(max_length=100, null=True, blank=True)
    permissions     = models.CharField(
        max_length=10,
        choices=[('public', 'Public'), ('private', 'Private')],
        default='private',
    )
    expiration_date = models.DateField(null=True, blank=True)
    uploaded_by     = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at      = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class AuditLog(models.Model):
    ACTION_CHOICES = (
        ('login',         'Login'),
        ('logout',        'Logout'),
        ('upload',        'File Upload'),
        ('download',      'File Download'),
        ('delete',        'File Delete'),
        ('failed_access', 'Failed Access'),
    )
    user       = models.ForeignKey(User, on_delete=models.CASCADE)
    action     = models.CharField(max_length=20, choices=ACTION_CHOICES)
    timestamp  = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.CharField(max_length=255, null=True, blank=True)
    file_name  = models.CharField(max_length=255, null=True, blank=True)
    details    = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.action} by {self.user.username} at {self.timestamp}"


class File(models.Model):
    """Encrypted file with admin approval workflow.

    Status flow:  pending → approved (user can download)
                  pending → rejected (user cannot download)

    Expiration lifecycle (managed by `delete_expired` command):
      1.  expiration_date - 3 days  →  warning email sent (warning_email_sent=True)
      2.  expiration_date reached    →  auto-extend by 10 days (auto_extended=True),
                                        notification email sent
      3.  expiration_date reached again (after auto-extension)
                                     →  file is deleted, deletion email sent
    """
    STATUS_PENDING  = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES  = [
        ('pending',  'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    file_metadata   = models.OneToOneField('FileMetadata', on_delete=models.CASCADE, null=True, blank=True)
    owner           = models.ForeignKey(User, on_delete=models.CASCADE)
    file            = models.FileField(upload_to='encrypted_files/', null=False, blank=False)
    description     = models.TextField(null=True, blank=True)
    tags            = models.CharField(max_length=255, blank=True, null=True)
    category        = models.CharField(max_length=100)
    permissions     = models.CharField(max_length=50, choices=[('public', 'Public'), ('private', 'Private')])
    expiration_date = models.DateField(null=True, blank=True)
    encrypted_key   = models.BinaryField(null=False, blank=False)
    hmac_signature  = models.CharField(max_length=64, blank=True, null=True)
    uploaded_at     = models.DateTimeField(auto_now_add=True)

    # Approval workflow fields
    status         = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)
    reviewed_by    = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name='reviewed_files'
    )
    reviewed_at    = models.DateTimeField(null=True, blank=True)
    rejection_note = models.TextField(blank=True, null=True)

    # ── Expiration workflow fields ──
    # True once the "your file is about to expire" warning email is sent.
    warning_email_sent = models.BooleanField(default=False)
    # True after the system has auto-extended the expiration by 10 days.
    auto_extended      = models.BooleanField(default=False)
    # When the warning email was sent (handy for audit / re-send logic).
    warning_sent_at    = models.DateTimeField(null=True, blank=True)
    # When the auto-extension was applied.
    auto_extended_at   = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.file_metadata.name if self.file_metadata else "No Metadata"

    @property
    def is_approved(self):
        return self.status == self.STATUS_APPROVED

    @property
    def is_pending(self):
        return self.status == self.STATUS_PENDING


class Block(models.Model):
    index         = models.IntegerField(unique=True)
    timestamp     = models.DateTimeField(auto_now_add=True)
    action        = models.CharField(max_length=50)
    username      = models.CharField(max_length=150)
    file_name     = models.CharField(max_length=255, blank=True, default='')
    file_hash     = models.CharField(max_length=64,  blank=True, default='')
    details       = models.TextField(blank=True, default='')
    previous_hash = models.CharField(max_length=64)
    block_hash    = models.CharField(max_length=64)

    class Meta:
        ordering = ['index']

    def __str__(self):
        return f"Block #{self.index} — {self.action} by {self.username}"

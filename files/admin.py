"""Admin configuration for the files app."""
from django.contrib import admin
from .models import File, FileMetadata, AuditLog, Block, UserKey


@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    list_display    = ('__str__', 'owner', 'status', 'uploaded_at', 'reviewed_by')
    list_filter     = ('status', 'permissions')
    search_fields   = ('owner__username', 'file_metadata__name')
    readonly_fields = ('uploaded_at', 'hmac_signature', 'encrypted_key', 'reviewed_at')


@admin.register(FileMetadata)
class FileMetadataAdmin(admin.ModelAdmin):
    list_display  = ('name', 'uploaded_by', 'file_type', 'size', 'created_at')
    search_fields = ('name', 'uploaded_by__username')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display    = ('action', 'user', 'ip_address', 'timestamp')
    list_filter     = ('action',)
    search_fields   = ('user__username', 'ip_address')
    readonly_fields = ('timestamp',)


@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display    = ('index', 'action', 'username', 'file_name', 'timestamp')
    readonly_fields = ('index', 'block_hash', 'previous_hash', 'timestamp')


admin.site.register(UserKey)

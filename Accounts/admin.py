"""Admin configuration for the Accounts app."""
from django.contrib import admin
from .models import OTP, Profile


@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    list_display  = ('user_email', 'created_at')
    readonly_fields = ('otp_hash', 'created_at')
    search_fields = ('user_email',)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display  = ('user', 'image')
    search_fields = ('user__username',)

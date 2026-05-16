"""Admin configuration for the monitoring app."""

from django.contrib import admin

from .models import UserActionLog

admin.site.register(UserActionLog)

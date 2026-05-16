"""
Root URL configuration for the project1 secure file storage system.

Routes requests to the appropriate Django app:
  - /admin/        Django admin
  - /Accounts/     Authentication (login, signup, OTP, profile)
  - /              Static pages (index, about, features, intro)
  - /files/        File management (upload, download, edit, delete)
  - /monitoring/   Admin dashboard
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('Accounts/', include('Accounts.urls')),
    path('', include('pages.urls')),
    path('files/', include(('files.urls', 'files'), namespace='files')),
    path('monitoring/', include('monitoring.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

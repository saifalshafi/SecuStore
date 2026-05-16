"""
Custom middleware for the project1 secure file storage system.
"""

from django.shortcuts import render
from django.http import Http404


class HideAdminMiddleware:
    """Protect the Django admin panel from unauthenticated / non-staff users.

    If a non-staff user (or anonymous visitor) requests any ``/admin/`` URL,
    they receive a custom 404 page instead of the admin login screen.  All
    genuine 404 responses are also rendered with the custom template.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Block non-staff users from discovering the admin panel.
        if request.path.startswith('/admin/'):
            if not request.user.is_authenticated or not request.user.is_staff:
                return render(request, 'pages/404.html', status=404)

        try:
            response = self.get_response(request)
            if response.status_code == 404:
                return render(request, 'pages/404.html', status=404)
        except Http404:
            return render(request, 'pages/404.html', status=404)

        return response

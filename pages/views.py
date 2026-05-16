"""Views for the pages app.

Serves static/public pages: landing page, about, features, navbar, and
the authenticated intro/dashboard page.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect


def index(request):
    """Landing page — redirects authenticated users to the intro page."""
    if request.user.is_authenticated:
        return redirect('intro')
    return render(request, 'pages/index.html', {'name': 'selena'})


def about(request):
    """Render the About page."""
    return render(request, 'pages/about.html')


def features(request):
    """Render the Features page."""
    return render(request, 'pages/features.html')


def navbar_view(request):
    """Render the standalone navbar template."""
    return render(request, 'myapp/navbar.html')


@login_required
def intro(request):
    """Render the intro/dashboard page for authenticated users."""
    return render(request, 'pages/intro.html')

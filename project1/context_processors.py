"""Custom template context processors for project1.

Injects per-request user statistics and profile data into every template
context so they are available globally without explicit view-level queries.
"""

from django.db.models import Sum

from files.models import File
from Accounts.models import Profile


def user_file_stats(request):
    """Inject file statistics and profile image URL for authenticated users.

    Returns a dict with:
      - ``user_total_files``: total number of files owned by the user.
      - ``user_storage_used``: total storage used in MB (rounded to 2 d.p.).
      - ``profile_image_url``: URL of the user's profile image, or ``None``
        if the default placeholder is in use.

    For unauthenticated requests an empty dict is returned.
    """
    if not request.user.is_authenticated:
        return {}

    user_files = File.objects.filter(owner=request.user)
    total_files = user_files.count()
    total_size = (
        user_files.aggregate(Sum('file_metadata__size'))['file_metadata__size__sum'] or 0
    )
    total_size_mb = round(total_size / (1024 * 1024), 2)

    profile_image_url = None
    profile, _created = Profile.objects.get_or_create(user=request.user)
    if profile.image and profile.image.name != 'profile_images/default.png':
        profile_image_url = profile.image.url

    return {
        'user_total_files': total_files,
        'user_storage_used': total_size_mb,
        'profile_image_url': profile_image_url,
    }

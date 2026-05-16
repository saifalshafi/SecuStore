"""URL configuration for the Accounts app.

All paths are mounted under ``/Accounts/`` by the root URL conf.
"""

from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views

urlpatterns = [
    # Login / Signup
    path('login/', views.login, name='login'),
    path('signup/', views.signup, name='signup'),

    # Signup OTP verification (Step 2 of signup)
    path('signup/verify_otp/', views.verify_signup_otp,  name='verify_signup_otp'),
    path('signup/resend_otp/', views.resend_signup_otp,  name='resend_signup_otp'),

    # Signup completion (Step 3 — collect name/username/password after email is verified)
    path('signup/details/',    views.signup_details,     name='signup_details'),

    # Logout (uses Django's built-in view)
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),

    # OTP verification (login)
    path('verify_otp/', views.verifyotp, name='verify_otp'),
    path('request_otp/', views.request_otp, name='request_otp'),

    path('password_reset/', views.password_reset_request, name='password_reset_request'),
    path('password_reset/confirm/<str:token>/', views.password_reset_confirm, name='password_reset_confirm'),


    path('share/create/<int:file_id>/', views.create_share_link,   name='create_share_link'),
    path('share/<str:token>/',          views.download_shared_file, name='download_shared_file'),

    # Password Change (now goes through OTP step)
    path('password_change/',                  views.password_change,                  name='password_change'),
    path('password_change/verify_otp/',       views.password_change_verify_otp,       name='password_change_verify_otp'),
    path('password_change/resend_otp/',       views.resend_password_change_otp,       name='resend_password_change_otp'),
    path(
        'password_change/done/',
        auth_views.PasswordChangeDoneView.as_view(
            template_name='pages/password_changed.html',
        ),
        name='password_change_done',
    ),

    # Profile
    path('profile/', views.profile, name='profile'),
    path('upload_profile_image/', views.upload_profile_image, name='upload_profile_image'),

    # Legal
    path('terms_conditions/', views.terms_conditions, name='terms_conditions'),
]

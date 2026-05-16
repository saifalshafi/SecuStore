"""URL configuration for the monitoring app."""
from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/',                  views.admin_dashboard_view,  name='admin_dashboard'),
    path('user/<int:user_id>/files/',   views.user_files_view,       name='user_files'),
    path('users/',                      views.admin_users_list,       name='admin_users_list'),
    path('users/<int:user_id>/toggle/', views.admin_toggle_user,      name='admin_toggle_user'),
    path('users/<int:user_id>/delete/', views.admin_delete_user,      name='admin_delete_user'),
    path('activity/',                   views.admin_activity_log,     name='admin_activity_log'),
    path('export/activity/',            views.export_activity_csv,    name='export_activity_csv'),
    path('export/files/',               views.export_files_csv,       name='export_files_csv'),
]

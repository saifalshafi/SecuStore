"""URL configuration for the files app."""
from django.urls import path
from . import views

app_name = "files"

urlpatterns = [
    # User
    path('',                         views.file_management_view,   name='file_management'),
    path('upload/',                  views.file_upload_view,       name='upload'),
    path('download/<int:file_id>/',  views.file_download_view,     name='file_download'),
    path('edit/<int:file_id>/',      views.edit_metadata,          name='edit_metadata'),
    path('admin/download/<int:file_id>/', views.admin_download_file, name='admin_download_file'),
    path('delete/<int:file_id>/',    views.delete_file,            name='delete_file'),
    # Admin
    path('admin/all/',                        views.admin_all_files_view,    name='admin_all_files'),
    path('admin/approve/<int:file_id>/',      views.admin_approve_file,      name='admin_approve_file'),
    path('admin/reject/<int:file_id>/',       views.admin_reject_file,       name='admin_reject_file'),
    path('admin/delete/<int:file_id>/',       views.admin_delete_file,       name='admin_delete_file'),
    path('admin/blockchain/',                 views.admin_verify_blockchain, name='admin_blockchain'),
]

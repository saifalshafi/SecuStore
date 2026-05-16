"""Forms for the files app.

Provides forms for editing file metadata and validating file uploads.
"""
from django import forms
from .models import FileMetadata

BLOCKED_EXTENSIONS = {'exe', 'bat', 'sh', 'dll', 'js', 'php', 'py', 'cmd', 'vbs', 'ps1', 'msi', 'scr', 'com', 'pif'}
MAX_FILE_SIZE = 50 * 1024 * 1024


class FileMetadataForm(forms.ModelForm):
    class Meta:
        model = FileMetadata
        fields = ['description', 'tags', 'category', 'permissions', 'expiration_date']


class FileUploadForm(forms.Form):
    file = forms.FileField()

    def clean_file(self):
        uploaded_file = self.cleaned_data.get('file')
        if uploaded_file:
            extension = uploaded_file.name.rsplit('.', 1)[-1].lower()
            if extension in BLOCKED_EXTENSIONS:
                raise forms.ValidationError(f"File type '.{extension}' is not allowed.")
            if uploaded_file.size > MAX_FILE_SIZE:
                raise forms.ValidationError("File size exceeds 50 MB limit.")
        return uploaded_file
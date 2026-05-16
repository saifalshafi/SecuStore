"""Migration: add expiration workflow fields to File.

Adds:
  - warning_email_sent  (whether the pre-expiration warning email was sent)
  - auto_extended       (whether the 10-day auto extension was applied)
  - warning_sent_at     (timestamp when warning was sent)
  - auto_extended_at    (timestamp when auto-extension was applied)
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('files', '0007_file_status_approval'),
    ]

    operations = [
        migrations.AddField(
            model_name='file',
            name='warning_email_sent',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='file',
            name='auto_extended',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='file',
            name='warning_sent_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='file',
            name='auto_extended_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]

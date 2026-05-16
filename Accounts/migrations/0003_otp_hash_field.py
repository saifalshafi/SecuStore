"""Migration: replace OTP.otp plain-text field with OTP.otp_hash (SHA-256)."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Accounts', '0002_profile'),
    ]

    operations = [
        migrations.AddField(
            model_name='otp',
            name='otp_hash',
            field=models.CharField(max_length=64, default=''),
            preserve_default=False,
        ),
        migrations.RemoveField(
            model_name='otp',
            name='otp',
        ),
    ]

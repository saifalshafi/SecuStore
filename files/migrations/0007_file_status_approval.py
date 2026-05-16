"""Migration: add file approval workflow fields."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('files', '0006_block'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.AddField(
            model_name='file', name='status',
            field=models.CharField(
                choices=[('pending','Pending Review'),('approved','Approved'),('rejected','Rejected')],
                default='pending', max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='file', name='reviewed_by',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='reviewed_files', to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='file', name='reviewed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='file', name='rejection_note',
            field=models.TextField(blank=True, null=True),
        ),
    ]

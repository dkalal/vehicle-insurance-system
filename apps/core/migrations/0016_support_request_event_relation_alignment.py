# Generated manually from Django's migration state diff output.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0015_support_request_event_state_alignment'),
        ('tenants', '0002_historicaltenant'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='supportrequestevent',
            name='created_by',
            field=models.ForeignKey(blank=True, help_text='User who created this record', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created_set', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='supportrequestevent',
            name='tenant',
            field=models.ForeignKey(help_text='Insurance company this record belongs to', on_delete=django.db.models.deletion.PROTECT, related_name='%(class)s_set', to='tenants.tenant'),
        ),
        migrations.AlterField(
            model_name='supportrequestevent',
            name='updated_by',
            field=models.ForeignKey(blank=True, help_text='User who last updated this record', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_updated_set', to=settings.AUTH_USER_MODEL),
        ),
    ]

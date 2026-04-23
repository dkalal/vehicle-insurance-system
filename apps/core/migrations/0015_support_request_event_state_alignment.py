# Generated manually to align support-request event migration state with Django's current model state.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0014_support_request_workflow_upgrade'),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name='supportrequestevent',
            name='core_suppor_tenant__6a7410_idx',
        ),
        migrations.RemoveIndex(
            model_name='supportrequestevent',
            name='core_suppor_created_9a8192_idx',
        ),
        migrations.RemoveIndex(
            model_name='supportrequestevent',
            name='core_suppor_updated_9e0e2e_idx',
        ),
        migrations.RemoveIndex(
            model_name='supportrequestevent',
            name='core_suppor_deleted_42da78_idx',
        ),
        migrations.RenameIndex(
            model_name='supportrequest',
            new_name='core_suppor_tenant__2bd480_idx',
            old_name='core_suppor_tenant__54865f_idx',
        ),
        migrations.RenameIndex(
            model_name='supportrequest',
            new_name='core_suppor_tenant__9c902f_idx',
            old_name='core_suppor_tenant__6f29db_idx',
        ),
        migrations.RenameIndex(
            model_name='supportrequestevent',
            new_name='core_suppor_tenant__b9b61e_idx',
            old_name='core_suppor_tenant__f04d5b_idx',
        ),
        migrations.RenameIndex(
            model_name='supportrequestevent',
            new_name='core_suppor_tenant__82166c_idx',
            old_name='core_suppor_tenant__7120bc_idx',
        ),
        migrations.AlterField(
            model_name='supportrequestevent',
            name='created_by',
            field=models.ForeignKey(blank=True, help_text='User who created this record', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='supportrequestevent_created_set', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='supportrequestevent',
            name='tenant',
            field=models.ForeignKey(db_index=True, help_text='Insurance company this record belongs to', on_delete=django.db.models.deletion.PROTECT, related_name='supportrequestevent_set', to='tenants.tenant'),
        ),
        migrations.AlterField(
            model_name='supportrequestevent',
            name='updated_by',
            field=models.ForeignKey(blank=True, help_text='User who last updated this record', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='supportrequestevent_updated_set', to=settings.AUTH_USER_MODEL),
        ),
    ]

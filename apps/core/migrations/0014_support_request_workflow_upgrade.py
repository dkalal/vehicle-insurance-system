# Generated manually for support workflow and dashboard upgrades.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def migrate_closed_to_resolved(apps, schema_editor):
    SupportRequest = apps.get_model('core', 'SupportRequest')
    SupportRequest.objects.filter(status='closed').update(status='resolved')


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0006_historicaluser_must_change_password_and_more'),
        ('core', '0013_delete_vehicleassignment'),
    ]

    operations = [
        migrations.AddField(
            model_name='supportrequest',
            name='permit_reference',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='supportrequest',
            name='policy_reference',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='supportrequest',
            name='request_type',
            field=models.CharField(
                choices=[
                    ('vehicle_compliance', 'Vehicle compliance issue'),
                    ('policy', 'Insurance/policy issue'),
                    ('permit', 'Permit/LATRA issue'),
                    ('payment', 'Payment issue'),
                    ('access', 'Staff access/account issue'),
                    ('data_correction', 'Data correction request'),
                    ('general', 'General support'),
                ],
                db_index=True,
                default='general',
                max_length=40,
            ),
        ),
        migrations.AddField(
            model_name='supportrequest',
            name='resolution_summary',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='supportrequest',
            name='vehicle_registration_number',
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AlterField(
            model_name='supportrequest',
            name='priority',
            field=models.CharField(
                choices=[('low', 'Low'), ('normal', 'Normal'), ('high', 'High')],
                db_index=True,
                default='normal',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='supportrequest',
            name='status',
            field=models.CharField(
                choices=[
                    ('open', 'Open'),
                    ('in_progress', 'In Progress'),
                    ('waiting_on_tenant', 'Waiting On Tenant'),
                    ('resolved', 'Resolved'),
                ],
                db_index=True,
                default='open',
                max_length=20,
            ),
        ),
        migrations.AddIndex(
            model_name='supportrequest',
            index=models.Index(fields=['tenant', 'request_type'], name='core_suppor_tenant__54865f_idx'),
        ),
        migrations.AddIndex(
            model_name='supportrequest',
            index=models.Index(fields=['tenant', 'priority'], name='core_suppor_tenant__6f29db_idx'),
        ),
        migrations.CreateModel(
            name='SupportRequestEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('deleted_at', models.DateTimeField(blank=True, db_index=True, help_text='Timestamp when record was soft-deleted', null=True)),
                ('event_type', models.CharField(choices=[('created', 'Created'), ('status_changed', 'Status changed'), ('assignment_changed', 'Assignment changed'), ('public_reply', 'Public reply'), ('internal_note', 'Internal note'), ('resolved', 'Resolved'), ('reopened', 'Reopened')], db_index=True, max_length=30)),
                ('visibility', models.CharField(choices=[('tenant', 'Tenant visible'), ('internal', 'Internal only')], db_index=True, default='tenant', max_length=20)),
                ('message', models.TextField(blank=True)),
                ('from_status', models.CharField(blank=True, max_length=20)),
                ('to_status', models.CharField(blank=True, max_length=20)),
                ('created_by', models.ForeignKey(blank=True, help_text='User who created this record', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='supportrequestevent_created_set', to=settings.AUTH_USER_MODEL)),
                ('new_assignee', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='support_new_assignment_events', to=settings.AUTH_USER_MODEL)),
                ('previous_assignee', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='support_previous_assignment_events', to=settings.AUTH_USER_MODEL)),
                ('support_request', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='events', to='core.supportrequest')),
                ('tenant', models.ForeignKey(db_index=True, help_text='Insurance company this record belongs to', on_delete=django.db.models.deletion.PROTECT, related_name='supportrequestevent_set', to='tenants.tenant')),
                ('updated_by', models.ForeignKey(blank=True, help_text='User who last updated this record', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='supportrequestevent_updated_set', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['created_at', 'id'],
                'indexes': [models.Index(fields=['tenant'], name='core_suppor_tenant__6a7410_idx'), models.Index(fields=['created_at'], name='core_suppor_created_9a8192_idx'), models.Index(fields=['updated_at'], name='core_suppor_updated_9e0e2e_idx'), models.Index(fields=['deleted_at'], name='core_suppor_deleted_42da78_idx'), models.Index(fields=['tenant', 'support_request', 'created_at'], name='core_suppor_tenant__f04d5b_idx'), models.Index(fields=['tenant', 'visibility', 'created_at'], name='core_suppor_tenant__7120bc_idx')],
            },
        ),
        migrations.RunPython(migrate_closed_to_resolved, reverse_code=migrations.RunPython.noop),
    ]

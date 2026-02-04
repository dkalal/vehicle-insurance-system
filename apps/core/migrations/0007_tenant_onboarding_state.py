from django.db import migrations, models
from django.conf import settings
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0006_rename_core_latra_ten_veh_stat_idx_core_latrar_tenant__c27395_idx_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='TenantOnboardingState',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('deleted_at', models.DateTimeField(blank=True, db_index=True, help_text='Timestamp when record was soft-deleted', null=True)),
                ('status', models.CharField(choices=[('not_started', 'Not started'), ('welcome_shown', 'Welcome shown'), ('company_setup', 'Company setup'), ('vehicle_basics', 'Vehicle basics'), ('vehicle_owner', 'Vehicle ownership'), ('vehicle_documents', 'Vehicle documents'), ('completed', 'Completed')], db_index=True, default='not_started', max_length=32)),
                ('current_step', models.CharField(blank=True, default='', max_length=32)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('created_by', models.ForeignKey(blank=True, help_text='User who created this record', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created_set', to=settings.AUTH_USER_MODEL)),
                ('first_vehicle', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='onboarding_first_for', to='core.vehicle')),
                ('tenant', models.ForeignKey(help_text='Insurance company this record belongs to', on_delete=django.db.models.deletion.PROTECT, related_name='%(class)s_set', to='tenants.tenant')),
                ('updated_by', models.ForeignKey(blank=True, help_text='User who last updated this record', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_updated_set', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Tenant onboarding state',
                'verbose_name_plural': 'Tenant onboarding states',
            },
        ),
        migrations.AddIndex(
            model_name='tenantonboardingstate',
            index=models.Index(fields=['tenant', 'status'], name='core_tenanton_tenant__status_idx'),
        ),
        migrations.AddConstraint(
            model_name='tenantonboardingstate',
            constraint=models.UniqueConstraint(condition=models.Q(('deleted_at__isnull', True)), fields=('tenant',), name='unique_onboarding_state_per_tenant'),
        ),
    ]

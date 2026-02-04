from django.db import migrations, models
from django.conf import settings
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0003_support_request'),
    ]

    operations = [
        migrations.CreateModel(
            name='PermitType',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('tenant', models.ForeignKey(help_text='Insurance company this record belongs to', on_delete=django.db.models.deletion.PROTECT, related_name='%(class)s_set', to='tenants.tenant')),
            ],
            options={
                'ordering': ['tenant_id', 'name'],
                'indexes': [
                    models.Index(fields=['tenant', 'name'], name='core_ptype_ten_name_idx'),
                ],
                'unique_together': {('tenant', 'name')},
            },
        ),
        migrations.CreateModel(
            name='LATRARecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('deleted_at', models.DateTimeField(blank=True, db_index=True, help_text='Timestamp when record was soft-deleted', null=True)),
                ('start_date', models.DateField()),
                ('end_date', models.DateField(blank=True, null=True)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('active', 'Active'), ('expired', 'Expired'), ('suspended', 'Suspended')], db_index=True, default='draft', max_length=20)),
                ('latra_number', models.CharField(max_length=100)),
                ('license_type', models.CharField(max_length=100)),
                ('route', models.CharField(blank=True, max_length=255)),
                ('issuing_authority', models.CharField(default='LATRA', max_length=100)),
                ('created_by', models.ForeignKey(blank=True, help_text='User who created this record', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created_set', to=settings.AUTH_USER_MODEL)),
                ('tenant', models.ForeignKey(help_text='Insurance company this record belongs to', on_delete=django.db.models.deletion.PROTECT, related_name='%(class)s_set', to='tenants.tenant')),
                ('updated_by', models.ForeignKey(blank=True, help_text='User who last updated this record', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_updated_set', to=settings.AUTH_USER_MODEL)),
                ('vehicle', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='%(class)s_set', to='core.vehicle')),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['tenant', 'vehicle', 'status'], name='core_latra_ten_veh_stat_idx'),
                    models.Index(fields=['tenant', 'latra_number'], name='core_latra_ten_latra_idx'),
                    models.Index(fields=['tenant', 'start_date'], name='core_latra_ten_start_idx'),
                    models.Index(fields=['tenant', 'end_date'], name='core_latra_ten_end_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='VehiclePermit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('deleted_at', models.DateTimeField(blank=True, db_index=True, help_text='Timestamp when record was soft-deleted', null=True)),
                ('start_date', models.DateField()),
                ('end_date', models.DateField(blank=True, null=True)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('active', 'Active'), ('expired', 'Expired'), ('suspended', 'Suspended')], db_index=True, default='draft', max_length=20)),
                ('reference_number', models.CharField(max_length=100)),
                ('document', models.FileField(blank=True, null=True, upload_to='vehicle_permits/')),
                ('created_by', models.ForeignKey(blank=True, help_text='User who created this record', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created_set', to=settings.AUTH_USER_MODEL)),
                ('permit_type', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='vehicle_permits', to='core.permittype')),
                ('tenant', models.ForeignKey(help_text='Insurance company this record belongs to', on_delete=django.db.models.deletion.PROTECT, related_name='%(class)s_set', to='tenants.tenant')),
                ('updated_by', models.ForeignKey(blank=True, help_text='User who last updated this record', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_updated_set', to=settings.AUTH_USER_MODEL)),
                ('vehicle', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='%(class)s_set', to='core.vehicle')),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['tenant', 'vehicle', 'status'], name='core_vehperm_ten_veh_stat_idx'),
                    models.Index(fields=['tenant', 'permit_type'], name='core_vehperm_ten_permit_idx'),
                    models.Index(fields=['tenant', 'start_date'], name='core_vehperm_ten_start_idx'),
                    models.Index(fields=['tenant', 'end_date'], name='core_vehperm_ten_end_idx'),
                ],
            },
        ),
    ]

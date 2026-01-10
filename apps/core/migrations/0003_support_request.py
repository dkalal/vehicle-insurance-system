from django.db import migrations, models
from django.conf import settings
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0002_alter_policy_policy_number_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='SupportRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('deleted_at', models.DateTimeField(blank=True, db_index=True, help_text='Timestamp when record was soft-deleted', null=True)),
                ('subject', models.CharField(max_length=255, db_index=True)),
                ('message', models.TextField()),
                ('status', models.CharField(choices=[('open', 'Open'), ('in_progress', 'In Progress'), ('closed', 'Closed')], db_index=True, default='open', max_length=20)),
                ('priority', models.CharField(db_index=True, default='normal', max_length=20)),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('created_by', models.ForeignKey(blank=True, help_text='User who created this record', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created_set', to=settings.AUTH_USER_MODEL)),
                ('tenant', models.ForeignKey(help_text='Insurance company this record belongs to', on_delete=django.db.models.deletion.PROTECT, related_name='%(class)s_set', to='tenants.tenant')),
                ('updated_by', models.ForeignKey(blank=True, help_text='User who last updated this record', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_updated_set', to=settings.AUTH_USER_MODEL)),
                ('assigned_to', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='support_assigned_set', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='supportrequest',
            index=models.Index(fields=['tenant', 'status'], name='core_suppor_tenant__status_idx'),
        ),
        migrations.AddIndex(
            model_name='supportrequest',
            index=models.Index(fields=['tenant', 'created_at'], name='core_suppor_tenant__created_idx'),
        ),
    ]

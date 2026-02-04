# Generated manually for unified lifecycle management

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_permittype_is_active'),
        ('accounts', '0001_initial'),
    ]

    operations = [
        # Policy model updates
        migrations.AddField(
            model_name='policy',
            name='cancelled_by',
            field=models.ForeignKey(
                blank=True,
                help_text='User who cancelled the policy',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='cancelled_policies',
                to='accounts.user'
            ),
        ),
        migrations.AlterField(
            model_name='policy',
            name='cancellation_reason',
            field=models.CharField(
                blank=True,
                choices=[
                    ('customer_request', 'Customer Request'),
                    ('non_payment', 'Non-Payment'),
                    ('vehicle_sold', 'Vehicle Sold'),
                    ('duplicate', 'Duplicate Entry'),
                    ('data_error', 'Data Error'),
                    ('other', 'Other')
                ],
                help_text='Reason for cancellation',
                max_length=50
            ),
        ),
        migrations.AddField(
            model_name='policy',
            name='cancellation_note',
            field=models.TextField(
                blank=True,
                help_text='Additional cancellation details'
            ),
        ),
        
        # VehiclePermit model updates
        migrations.AddField(
            model_name='vehiclepermit',
            name='activated_at',
            field=models.DateTimeField(
                blank=True,
                help_text='When record was activated',
                null=True
            ),
        ),
        migrations.AddField(
            model_name='vehiclepermit',
            name='cancelled_at',
            field=models.DateTimeField(
                blank=True,
                help_text='When record was cancelled',
                null=True
            ),
        ),
        migrations.AddField(
            model_name='vehiclepermit',
            name='cancelled_by',
            field=models.ForeignKey(
                blank=True,
                help_text='User who cancelled the record',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='cancelled_vehiclepermit_set',
                to='accounts.user'
            ),
        ),
        migrations.AddField(
            model_name='vehiclepermit',
            name='cancellation_reason',
            field=models.CharField(
                blank=True,
                choices=[
                    ('customer_request', 'Customer Request'),
                    ('vehicle_sold', 'Vehicle Sold'),
                    ('duplicate', 'Duplicate Entry'),
                    ('data_error', 'Data Error'),
                    ('expired_early', 'Expired Early'),
                    ('other', 'Other')
                ],
                help_text='Reason for cancellation',
                max_length=50
            ),
        ),
        migrations.AddField(
            model_name='vehiclepermit',
            name='cancellation_note',
            field=models.TextField(
                blank=True,
                help_text='Additional cancellation details'
            ),
        ),
        migrations.AlterField(
            model_name='vehiclepermit',
            name='status',
            field=models.CharField(
                choices=[
                    ('draft', 'Draft'),
                    ('active', 'Active'),
                    ('expired', 'Expired'),
                    ('cancelled', 'Cancelled')
                ],
                db_index=True,
                default='draft',
                max_length=20
            ),
        ),
        
        # LATRARecord model updates
        migrations.AddField(
            model_name='latrarecord',
            name='activated_at',
            field=models.DateTimeField(
                blank=True,
                help_text='When record was activated',
                null=True
            ),
        ),
        migrations.AddField(
            model_name='latrarecord',
            name='cancelled_at',
            field=models.DateTimeField(
                blank=True,
                help_text='When record was cancelled',
                null=True
            ),
        ),
        migrations.AddField(
            model_name='latrarecord',
            name='cancelled_by',
            field=models.ForeignKey(
                blank=True,
                help_text='User who cancelled the record',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='cancelled_latrarecord_set',
                to='accounts.user'
            ),
        ),
        migrations.AddField(
            model_name='latrarecord',
            name='cancellation_reason',
            field=models.CharField(
                blank=True,
                choices=[
                    ('customer_request', 'Customer Request'),
                    ('vehicle_sold', 'Vehicle Sold'),
                    ('duplicate', 'Duplicate Entry'),
                    ('data_error', 'Data Error'),
                    ('expired_early', 'Expired Early'),
                    ('other', 'Other')
                ],
                help_text='Reason for cancellation',
                max_length=50
            ),
        ),
        migrations.AddField(
            model_name='latrarecord',
            name='cancellation_note',
            field=models.TextField(
                blank=True,
                help_text='Additional cancellation details'
            ),
        ),
        migrations.AlterField(
            model_name='latrarecord',
            name='status',
            field=models.CharField(
                choices=[
                    ('draft', 'Draft'),
                    ('active', 'Active'),
                    ('expired', 'Expired'),
                    ('cancelled', 'Cancelled')
                ],
                db_index=True,
                default='draft',
                max_length=20
            ),
        ),
    ]

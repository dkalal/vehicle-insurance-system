from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_vehicle_compliance'),
    ]

    operations = [
        migrations.AddField(
            model_name='permittype',
            name='conflicts_with',
            field=models.ManyToManyField(blank=True, to='core.permittype'),
        ),
    ]

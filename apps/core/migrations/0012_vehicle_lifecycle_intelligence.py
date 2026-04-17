# Generated manually to restore Vehicle lifecycle fields in Django state.

from django.db import migrations, models


def add_vehicle_lifecycle_columns(apps, schema_editor):
    column_sql = {
        "lifecycle_state": "varchar(20) NOT NULL DEFAULT 'active'",
        "usage_context": "varchar(100) NULL",
    }

    with schema_editor.connection.cursor() as cursor:
        for table_name in ("core_vehicle", "core_historicalvehicle"):
            existing_columns = {
                column.name
                for column in schema_editor.connection.introspection.get_table_description(
                    cursor,
                    table_name,
                )
            }
            quoted_table = schema_editor.quote_name(table_name)
            for column_name, definition in column_sql.items():
                if column_name in existing_columns:
                    continue
                quoted_column = schema_editor.quote_name(column_name)
                schema_editor.execute(
                    f"ALTER TABLE {quoted_table} ADD COLUMN {quoted_column} {definition}"
                )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0011_unified_lifecycle_management"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    add_vehicle_lifecycle_columns,
                    reverse_code=migrations.RunPython.noop,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="vehicle",
                    name="lifecycle_state",
                    field=models.CharField(
                        choices=[
                            ("active", "Active"),
                            ("inactive", "Inactive"),
                            ("archived", "Archived"),
                        ],
                        db_index=True,
                        default="active",
                        help_text="Operational lifecycle state for this vehicle",
                        max_length=20,
                    ),
                ),
                migrations.AddField(
                    model_name="vehicle",
                    name="usage_context",
                    field=models.CharField(
                        blank=True,
                        help_text="Optional context describing how this vehicle is used",
                        max_length=100,
                        null=True,
                    ),
                ),
                migrations.AddField(
                    model_name="historicalvehicle",
                    name="lifecycle_state",
                    field=models.CharField(
                        choices=[
                            ("active", "Active"),
                            ("inactive", "Inactive"),
                            ("archived", "Archived"),
                        ],
                        db_index=True,
                        default="active",
                        help_text="Operational lifecycle state for this vehicle",
                        max_length=20,
                    ),
                ),
                migrations.AddField(
                    model_name="historicalvehicle",
                    name="usage_context",
                    field=models.CharField(
                        blank=True,
                        help_text="Optional context describing how this vehicle is used",
                        max_length=100,
                        null=True,
                    ),
                ),
            ],
        ),
    ]

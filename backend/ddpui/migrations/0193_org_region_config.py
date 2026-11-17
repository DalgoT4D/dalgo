# Generated for multi-region Airbyte (T1)

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ddpui", "0192_notification_type_field"),
    ]

    operations = [
        migrations.AddField(
            model_name="org",
            name="region_config",
            field=models.JSONField(
                help_text="Data region of this org: {aws_region, country, airbyte_secret_name}. Validated by OrgRegionConfig. NULL is treated as the home region (Mumbai).",
                null=True,
            ),
        ),
    ]

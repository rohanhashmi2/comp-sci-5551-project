import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inspections", "0005_alter_inspectionresult_deadline"),
    ]

    operations = [
        migrations.AddField(
            model_name="inspection",
            name="previous_inspection",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="follow_ups",
                to="inspections.inspection",
            ),
        ),
    ]

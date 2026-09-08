from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("examc_app", "0014_unrecognized_review_scan"),
    ]

    operations = [
        migrations.AddField(
            model_name="unrecognizedreviewscan",
            name="deleted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]

from django.db import migrations
from django.db import models


class Migration(migrations.Migration):
    dependencies = [
        ("paperless", "0004_applicationconfiguration_barcode_asn_prefix_and_more"),
    ]

    operations = [
        migrations.add_field(
            model_name="applicationconfiguration",
            name="split_pdf_enabled",
            field=models.BooleanField(
                default=False,
                verbose_name="Enable splitting of multi-page PDFs",
            ),
        ),
    ]

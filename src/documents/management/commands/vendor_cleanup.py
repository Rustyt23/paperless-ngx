from django.core.management.base import BaseCommand

from documents.models import Correspondent
from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import Tag
from documents.utils.vendor_guard import BLOCKLIST
from documents.utils.vendor_guard import normalize_invoice_date
from documents.utils.vendor_guard import normalize_name


class Command(BaseCommand):
    help = "Cleanup blocked correspondents and normalize invoice dates"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--verbose", action="store_true")

    def handle(self, *args, **opts):
        dry = opts.get("dry_run")
        verbose = opts.get("verbose")

        needs_vendor, _ = Tag.objects.get_or_create(name="needs-vendor")
        needs_date, _ = Tag.objects.get_or_create(name="needs-date")

        # Handle correspondents on blocklist
        for corr in Correspondent.objects.all():
            if normalize_name(corr.name) in BLOCKLIST:
                docs = Document.objects.filter(correspondent=corr)
                count = docs.count()
                if verbose:
                    self.stdout.write(f"Unassigning {count} docs from {corr.name}")
                if not dry:
                    docs.update(correspondent=None)
                    for doc in docs:
                        doc.tags.add(needs_vendor)

        # Normalize invoice date field if present
        try:
            invoice_field = CustomField.objects.get(name__iexact="Invoice Date")
        except CustomField.DoesNotExist:
            invoice_field = None

        if (
            invoice_field
            and invoice_field.data_type == CustomField.FieldDataType.STRING
        ):
            for inst in CustomFieldInstance.objects.filter(field=invoice_field):
                current = inst.value_text or ""
                normalized = normalize_invoice_date(current)
                if normalized:
                    if normalized != current and not dry:
                        inst.value_text = normalized
                        inst.save(update_fields=("value_text",))
                        if verbose:
                            self.stdout.write(
                                f"Normalized date for doc {inst.document_id}",
                            )
                else:
                    if verbose:
                        self.stdout.write(
                            f"Could not parse date for doc {inst.document_id}",
                        )
                    if not dry:
                        inst.document.tags.add(needs_date)

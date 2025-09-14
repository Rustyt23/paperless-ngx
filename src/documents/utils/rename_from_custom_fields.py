from __future__ import annotations

import datetime
import re

from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document

ILLEGAL_CHARS = r'[\\/:*?"<>|]'


def get_cf_value(document: Document, field_name: str):
    try:
        field = CustomField.objects.get(name=field_name)
    except CustomField.DoesNotExist:
        return None
    try:
        instance = document.custom_fields.get(field=field)
    except CustomFieldInstance.DoesNotExist:
        return None
    if field.data_type == CustomField.FieldDataType.DATE:
        return instance.value_date
    return instance.value_text


def sanitize_vendor(name: str) -> str:
    name = re.sub(r"\s+", " ", name).strip()
    name = re.sub(ILLEGAL_CHARS, "", name)
    return name.replace(" ", "_")


def compute_title(document: Document) -> str | None:
    vendor_field = CustomField.objects.filter(name="Vendor Name").first()
    invoice_field = CustomField.objects.filter(name="Invoice Date").first()

    vendor_value = None
    if vendor_field:
        vendor_instance = document.custom_fields.filter(field=vendor_field).first()
        if vendor_instance:
            vendor_value = vendor_instance.value_text
    if not vendor_value and document.correspondent:
        vendor_value = document.correspondent.name
    if not vendor_value:
        return None

    invoice_value = None
    if invoice_field:
        invoice_instance = document.custom_fields.filter(field=invoice_field).first()
        if invoice_instance:
            if invoice_field.data_type == CustomField.FieldDataType.DATE:
                invoice_value = invoice_instance.value_date
            else:
                text = invoice_instance.value_text
                try:
                    invoice_value = datetime.date.fromisoformat(text)
                except ValueError:
                    return None
    if not invoice_value:
        return None

    vendor_sanitized = sanitize_vendor(vendor_value)
    date_str = invoice_value.strftime("%d-%m-%Y")
    base = f"{vendor_sanitized}_{date_str}"

    vendor_docs = None
    if vendor_field and document.custom_fields.filter(field=vendor_field).exists():
        vendor_docs = Document.objects.filter(
            custom_fields__field=vendor_field,
            custom_fields__value_text=vendor_value,
        )
    else:
        vendor_docs = Document.objects.filter(correspondent__name=vendor_value)

    if invoice_field.data_type == CustomField.FieldDataType.DATE:
        date_docs = Document.objects.filter(
            custom_fields__field=invoice_field,
            custom_fields__value_date=invoice_value,
        )
    else:
        date_docs = Document.objects.filter(
            custom_fields__field=invoice_field,
            custom_fields__value_text=invoice_value.isoformat(),
        )

    existing = (
        vendor_docs.filter(pk__in=date_docs.values("pk"))
        .exclude(pk=document.pk)
        .count()
    )

    if existing == 0:
        return base
    return f"{base} ({existing + 1})"

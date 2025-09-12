from __future__ import annotations

import datetime
import re

from django.db.models import Q

from documents.models import CustomField
from documents.models import Document

ILLEGAL_CHARS = r'[\\/:*?"<>|]'


def clean_vendor(name: str) -> str:
    name = name.strip()
    name = re.sub(r"[_\-.]+", " ", name)
    name = re.sub(ILLEGAL_CHARS, "", name)
    name = re.sub(r"\s+", " ", name)
    while name and not name[0].isalnum():
        if name[0] == "(" and ")" in name:
            break
        name = name[1:]
    while name and not name[-1].isalnum():
        if name[-1] == ")" and "(" in name:
            break
        name = name[:-1]
    return name.strip()


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

    vendor_cleaned = clean_vendor(vendor_value)
    if not vendor_cleaned:
        return None
    date_str = invoice_value.strftime("%m-%d-%Y")
    base = f"{vendor_cleaned} {date_str}"

    if vendor_field:
        vendor_docs = Document.objects.filter(
            Q(custom_fields__field=vendor_field, custom_fields__value_text=vendor_value)
            | Q(correspondent__name=vendor_value),
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
        .distinct()
        .count()
    )

    if existing == 0:
        return base
    return f"{base} ({existing + 1})"

from __future__ import annotations

import re

from documents.models import CustomField
from documents.models import Document
from documents.utils.vendor_guard import BLOCKLIST
from documents.utils.vendor_guard import normalize_invoice_date
from documents.utils.vendor_guard import normalize_name

ILLEGAL_CHARS = r'[\\/:*?"<>|]'


def _clean_correspondent(name: str) -> str:
    name = name.strip()
    name = re.sub(r"[_-]+", " ", name)
    name = re.sub(ILLEGAL_CHARS, "", name)
    name = re.sub(r"[.,]", "", name)
    name = re.sub(r"\s+", " ", name)
    return name.strip(" &+,'().")


def compute_title(document: Document) -> str | None:
    vendor_cf = CustomField.objects.filter(name__iexact="Vendor Name").first()
    invoice_cf = CustomField.objects.filter(name__iexact="Invoice Date").first()

    vendor = None
    if document.correspondent:
        vendor = getattr(
            document.correspondent,
            "display_name",
            document.correspondent.name,
        )
    elif vendor_cf:
        inst = document.custom_fields.filter(field=vendor_cf).first()
        if inst:
            vendor = inst.value_text
    if not vendor or normalize_name(vendor) in BLOCKLIST:
        return None

    clean_vendor = _clean_correspondent(vendor)
    if not clean_vendor:
        return None

    if not invoice_cf:
        return None
    inst = document.custom_fields.filter(field=invoice_cf).first()
    if not inst:
        return None

    if invoice_cf.data_type == CustomField.FieldDataType.DATE:
        if not inst.value_date:
            return None
        date_str = inst.value_date.strftime("%m-%d-%Y")
        date_filter = {
            "custom_fields__field": invoice_cf,
            "custom_fields__value_date": inst.value_date,
        }
    else:
        date_str = normalize_invoice_date(inst.value_text)
        if not date_str:
            return None
        date_filter = {
            "custom_fields__field": invoice_cf,
            "custom_fields__value_text": date_str,
        }

    base = f"{clean_vendor} {date_str}"
    docs_same_date = Document.objects.filter(**date_filter)

    duplicates = 0
    if document.correspondent_id is not None:
        duplicates = (
            docs_same_date.filter(correspondent_id=document.correspondent_id)
            .exclude(pk=document.pk)
            .count()
        )
    else:
        qs = docs_same_date.exclude(pk=document.pk).select_related("correspondent")
        for other in qs:
            other_name = None
            if other.correspondent:
                other_name = getattr(
                    other.correspondent,
                    "display_name",
                    other.correspondent.name,
                )
            elif vendor_cf:
                other_inst = other.custom_fields.filter(field=vendor_cf).first()
                if other_inst:
                    other_name = other_inst.value_text
            if other_name and _clean_correspondent(other_name) == clean_vendor:
                duplicates += 1

    if duplicates:
        return f"{base} ({duplicates + 1})"
    return base

from __future__ import annotations

import datetime

from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document

INVOICE_DATE_FIELD_NAME = "Invoice Date"


def _iso_to_date(value: str | datetime.date) -> datetime.date | None:
    if isinstance(value, datetime.date):
        return value
    try:
        return datetime.date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def get_invoice_date(
    document: Document,
) -> tuple[datetime.date | None, CustomField | None]:
    try:
        field = CustomField.objects.get(name=INVOICE_DATE_FIELD_NAME)
    except CustomField.DoesNotExist:
        return None, None
    try:
        instance = document.custom_fields.get(field=field)
    except CustomFieldInstance.DoesNotExist:
        return None, field
    return _iso_to_date(instance.value), field


def format_dmy(date_obj: datetime.date) -> str:
    return date_obj.strftime("%d-%m-%Y")

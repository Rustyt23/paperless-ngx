import datetime

from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document


def create_doc(vendor_field, invoice_field, vendor_value, invoice_value, checksum):
    doc = Document.objects.create(
        checksum=checksum,
        mime_type="application/pdf",
        content="",
    )
    if vendor_value is not None:
        CustomFieldInstance.objects.create(
            document=doc, field=vendor_field, value_text=vendor_value,
        )
    if invoice_value is not None:
        CustomFieldInstance.objects.create(
            document=doc, field=invoice_field, value_date=invoice_value,
        )
    doc.refresh_from_db()
    return doc


def test_rename_documents_same_vendor_numbered(db):
    vendor_field = CustomField.objects.create(
        name="Vendor Name", data_type=CustomField.FieldDataType.STRING,
    )
    invoice_field = CustomField.objects.create(
        name="Invoice Date", data_type=CustomField.FieldDataType.DATE,
    )
    date = datetime.date(2024, 10, 2)

    doc1 = create_doc(vendor_field, invoice_field, "Thanos", date, "0" * 32)
    doc2 = create_doc(vendor_field, invoice_field, "Thanos", date, "1" * 32)
    doc3 = create_doc(vendor_field, invoice_field, "Thanos", date, "2" * 32)

    assert doc1.title == "Thanos_02-10-2024"
    assert doc2.title == "Thanos_02-10-2024 (2)"
    assert doc3.title == "Thanos_02-10-2024 (3)"

    other_date = datetime.date(2024, 10, 3)
    doc4 = create_doc(vendor_field, invoice_field, "Thanos", other_date, "3" * 32)
    assert doc4.title == "Thanos_03-10-2024"


def test_missing_fields_leave_title(db):
    vendor_field = CustomField.objects.create(
        name="Vendor Name", data_type=CustomField.FieldDataType.STRING,
    )
    invoice_field = CustomField.objects.create(
        name="Invoice Date", data_type=CustomField.FieldDataType.DATE,
    )

    doc = create_doc(vendor_field, invoice_field, "Thanos", None, "4" * 32)
    assert doc.title == ""

    doc2 = create_doc(
        vendor_field, invoice_field, None, datetime.date(2024, 10, 2), "5" * 32,
    )
    assert doc2.title == ""


def test_title_recomputed_on_field_update(db, mocker):
    vendor_field = CustomField.objects.create(
        name="Vendor Name", data_type=CustomField.FieldDataType.STRING,
    )
    invoice_field = CustomField.objects.create(
        name="Invoice Date", data_type=CustomField.FieldDataType.DATE,
    )
    doc = Document.objects.create(
        checksum="6" * 32,
        mime_type="application/pdf",
        content="",
    )

    CustomFieldInstance.objects.create(
        document=doc, field=vendor_field, value_text="Thanos",
    )
    doc.refresh_from_db()
    assert doc.title == ""

    with mocker.patch(
        "documents.signals.handlers.Document.save", wraps=Document.save,
    ) as mock_save:
        CustomFieldInstance.objects.create(
            document=doc, field=invoice_field, value_date=datetime.date(2024, 10, 2),
        )
        doc.refresh_from_db()
        assert doc.title == "Thanos_02-10-2024"
        assert mock_save.call_count == 1

    with mocker.patch(
        "documents.signals.handlers.Document.save", wraps=Document.save,
    ) as mock_save2:
        doc.save()
        assert mock_save2.call_count == 1
    assert doc.title == "Thanos_02-10-2024"

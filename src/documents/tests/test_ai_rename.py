import datetime

from documents.models import Correspondent
from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document


def _create_document(corr, field, date, checksum):
    doc = Document.objects.create(
        correspondent=corr,
        checksum=checksum,
        mime_type="application/pdf",
        content="",
    )
    CustomFieldInstance.objects.create(document=doc, field=field, value_date=date)
    doc.save()
    doc.refresh_from_db()
    return doc


def test_rename_documents_same_vendor_numbered(db):
    corr = Correspondent.objects.create(name="Vendor")
    field = CustomField.objects.create(
        name="Invoice Date",
        data_type=CustomField.FieldDataType.DATE,
    )
    date = datetime.date(2024, 10, 2)

    doc1 = _create_document(corr, field, date, "0" * 32)
    doc2 = _create_document(corr, field, date, "1" * 32)
    doc3 = _create_document(corr, field, date, "2" * 32)

    assert doc1.title == "Vendor_02-10-2024 (1)"
    assert doc2.title == "Vendor_02-10-2024 (2)"
    assert doc3.title == "Vendor_02-10-2024 (3)"

    other_date = datetime.date(2024, 10, 3)
    doc4 = _create_document(corr, field, other_date, "3" * 32)
    assert doc4.title == "Vendor_03-10-2024 (1)"


def test_rename_idempotent(db, mocker):
    corr = Correspondent.objects.create(name="Vendor")
    field = CustomField.objects.create(
        name="Invoice Date",
        data_type=CustomField.FieldDataType.DATE,
    )
    date = datetime.date(2024, 10, 2)
    doc = _create_document(corr, field, date, "4" * 32)

    with mocker.patch(
        "documents.signals.handlers.Document.save",
        wraps=Document.save,
    ) as mock_save:
        doc.save()
        assert mock_save.call_count == 1

    doc.refresh_from_db()
    assert doc.title == "Vendor_02-10-2024 (1)"

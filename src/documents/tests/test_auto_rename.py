import datetime

from documents.models import Correspondent
from documents.models import Document


def test_title_renamed_same_vendor_numbered(db):
    corr = Correspondent.objects.create(name="Acme Corp")
    created_date = datetime.date(2024, 9, 11)

    doc1 = Document.objects.create(
        correspondent=corr,
        checksum="0" * 32,
        mime_type="application/pdf",
        content="",
        created=created_date,
    )
    doc2 = Document.objects.create(
        correspondent=corr,
        checksum="1" * 32,
        mime_type="application/pdf",
        content="",
        created=created_date,
    )

    doc1.refresh_from_db()
    doc2.refresh_from_db()

    assert doc1.title == "Acme_Corp_2024-09-11_1"
    assert doc2.title == "Acme_Corp_2024-09-11_2"


def test_title_renamed_unknown_vendor(db):
    created_date = datetime.date(2024, 9, 11)

    doc = Document.objects.create(
        checksum="0" * 32,
        mime_type="application/pdf",
        content="",
        created=created_date,
    )

    doc.refresh_from_db()

    assert doc.title == "UnknownVendor_2024-09-11"

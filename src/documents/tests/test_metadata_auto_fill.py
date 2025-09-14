import datetime

from documents.models import Document


def test_puritan_bakery_correspondent(db):
    doc = Document.objects.create(
        checksum="a" * 32,
        mime_type="application/pdf",
        content="Puritan Bakery, Inc.\nInvoice",
    )
    doc.refresh_from_db()
    assert doc.correspondent is not None
    assert doc.correspondent.name == "Puritan Bakery"


def test_date_extracted(db):
    doc = Document.objects.create(
        checksum="b" * 32, mime_type="application/pdf", content="Date: 1/27/25",
    )
    doc.refresh_from_db()
    assert doc.created == datetime.date(2025, 1, 27)


def test_orange_county_mapping(db):
    doc = Document.objects.create(
        checksum="c" * 32, mime_type="application/pdf", content="Orange Country Pumping",
    )
    doc.refresh_from_db()
    assert doc.correspondent is not None
    assert doc.correspondent.name == "Orange County Pumping"

from documents.models import Correspondent
from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.utils.ocr_stats import OCRStats


def create_doc(checksum):
    return Document.objects.create(
        checksum=checksum,
        mime_type="application/pdf",
        content="",
    )


def test_blocked_correspondent_assignment(db):
    corr = Correspondent.objects.create(name="Private")
    doc = Document.objects.create(
        checksum="0" * 32,
        mime_type="application/pdf",
        correspondent=corr,
        content="",
    )
    doc.refresh_from_db()
    assert doc.correspondent is None
    assert {t.name for t in doc.tags.all()} == {"needs-vendor"}


def test_blocked_correspondent_creation(db):
    corr = Correspondent.objects.create(name="Gourmet Pie")
    doc = Document.objects.create(
        checksum="1" * 32,
        mime_type="application/pdf",
        correspondent=corr,
        content="",
    )
    doc.refresh_from_db()
    assert doc.correspondent is None
    assert {t.name for t in doc.tags.all()} == {"needs-vendor"}


def test_auto_assign_from_custom_field(db):
    corr = Correspondent.objects.create(name="Puritan Bakery Inc")
    vendor_field = CustomField.objects.create(
        name="Vendor Name",
        data_type=CustomField.FieldDataType.STRING,
    )
    doc = create_doc("2" * 32)
    CustomFieldInstance.objects.create(
        document=doc,
        field=vendor_field,
        value_text="Puritan Bakery, Inc.",
    )
    doc.refresh_from_db()
    assert doc.correspondent == corr


def test_blocked_vendor_name_from_custom_field(db):
    vendor_field = CustomField.objects.create(
        name="Vendor Name",
        data_type=CustomField.FieldDataType.STRING,
    )
    doc = create_doc("3" * 32)
    CustomFieldInstance.objects.create(
        document=doc,
        field=vendor_field,
        value_text="Oak Wantana",
    )
    doc.refresh_from_db()
    assert doc.correspondent is None
    assert {t.name for t in doc.tags.all()} == {"needs-vendor"}


def test_invoice_date_enforcement(db):
    date_field = CustomField.objects.create(
        name="Invoice Date",
        data_type=CustomField.FieldDataType.STRING,
    )
    d1 = create_doc("4" * 32)
    cf1 = CustomFieldInstance.objects.create(
        document=d1,
        field=date_field,
        value_text="2024-08-06",
    )
    cf1.refresh_from_db()
    assert cf1.value_text == "08-06-2024"

    d2 = create_doc("5" * 32)
    cf2 = CustomFieldInstance.objects.create(
        document=d2,
        field=date_field,
        value_text="9/8/25 4:04 AM",
    )
    cf2.refresh_from_db()
    assert cf2.value_text == "09-08-2025"

    d3 = create_doc("6" * 32)
    cf3 = CustomFieldInstance.objects.create(
        document=d3,
        field=date_field,
        value_text="08/09/2025",
    )
    cf3.refresh_from_db()
    assert cf3.value_text == "08-09-2025"

    d4 = create_doc("7" * 32)
    cf4 = CustomFieldInstance.objects.create(
        document=d4,
        field=date_field,
        value_text="not a date",
    )
    cf4.refresh_from_db()
    assert cf4.value_text == "not a date"
    assert {t.name for t in d4.tags.all()} == {"needs-date"}


def test_title_from_correspondent_and_date(db):
    corr = Correspondent.objects.create(name="Jose Gutierrez")
    date_field = CustomField.objects.create(
        name="Invoice Date",
        data_type=CustomField.FieldDataType.STRING,
    )
    doc = Document.objects.create(
        checksum="8" * 32,
        mime_type="application/pdf",
        correspondent=corr,
        content="",
    )
    CustomFieldInstance.objects.create(
        document=doc,
        field=date_field,
        value_text="2023-01-10",
    )
    doc.refresh_from_db()
    assert doc.title == "Jose Gutierrez 01-10-2023"


def test_title_cleaning(db):
    corr = Correspondent.objects.create(name="All American Sign Company, Inc.")
    date_field = CustomField.objects.create(
        name="Invoice Date",
        data_type=CustomField.FieldDataType.STRING,
    )
    doc = Document.objects.create(
        checksum="9" * 32,
        mime_type="application/pdf",
        correspondent=corr,
        content="",
    )
    CustomFieldInstance.objects.create(
        document=doc,
        field=date_field,
        value_text="08/12/2024",
    )
    doc.refresh_from_db()
    assert doc.title == "All American Sign Company Inc 08-12-2024"


def test_title_blocked_vendor(db):
    corr = Correspondent.objects.create(name="Oak_Wantana")
    date_field = CustomField.objects.create(
        name="Invoice Date",
        data_type=CustomField.FieldDataType.STRING,
    )
    doc = Document.objects.create(
        checksum="a" * 32,
        mime_type="application/pdf",
        correspondent=corr,
        content="",
    )
    CustomFieldInstance.objects.create(
        document=doc,
        field=date_field,
        value_text="07-24-2024",
    )
    doc.refresh_from_db()
    assert doc.title == ""


def test_title_duplicate_suffix(db):
    corr = Correspondent.objects.create(name="Jose Gutierrez")
    date_field = CustomField.objects.create(
        name="Invoice Date",
        data_type=CustomField.FieldDataType.STRING,
    )
    d1 = Document.objects.create(
        checksum="b" * 32,
        mime_type="application/pdf",
        correspondent=corr,
        content="",
    )
    CustomFieldInstance.objects.create(
        document=d1,
        field=date_field,
        value_text="1/10/23",
    )
    d1.refresh_from_db()
    assert d1.title == "Jose Gutierrez 01-10-2023"

    d2 = Document.objects.create(
        checksum="c" * 32,
        mime_type="application/pdf",
        correspondent=corr,
        content="",
    )
    CustomFieldInstance.objects.create(
        document=d2,
        field=date_field,
        value_text="01-10-2023",
    )
    d2.refresh_from_db()
    assert d2.title == "Jose Gutierrez 01-10-2023 (2)"

    d3 = Document.objects.create(
        checksum="d" * 32,
        mime_type="application/pdf",
        correspondent=corr,
        content="",
    )
    CustomFieldInstance.objects.create(
        document=d3,
        field=date_field,
        value_text="01-10-2023",
    )
    d3.refresh_from_db()
    assert d3.title == "Jose Gutierrez 01-10-2023 (3)"


def test_small_ocr_sets_unidentified(db, monkeypatch):
    def fake_stats(path, content):
        return (
            OCRStats(word_count=5, char_count=25, has_text_layer=True),
            OCRStats(word_count=5, char_count=25, has_text_layer=True),
        )

    monkeypatch.setattr(
        "documents.signals.handlers.get_ocr_stats",
        fake_stats,
    )
    doc = Document.objects.create(
        checksum="e" * 32,
        mime_type="application/pdf",
        content="",
    )
    doc.refresh_from_db()
    assert doc.correspondent.name == "Unidentified"
    cf = CustomField.objects.get(name="Vendor Name")
    cfi = CustomFieldInstance.objects.get(document=doc, field=cf)
    assert cfi.value_text == "Unidentified"
    assert {t.name for t in doc.tags.all()} == {"needs-vendor"}


def test_remove_needs_vendor_tag(db, monkeypatch):
    def fake_stats(path, content):
        return (
            OCRStats(word_count=0, char_count=0, has_text_layer=False),
            OCRStats(word_count=0, char_count=0, has_text_layer=False),
        )

    monkeypatch.setattr(
        "documents.signals.handlers.get_ocr_stats",
        fake_stats,
    )
    doc = Document.objects.create(
        checksum="f" * 32,
        mime_type="application/pdf",
        content="",
    )
    corr = Correspondent.objects.create(name="Acme Corp")
    doc.correspondent = corr
    doc.save(update_fields=("correspondent",))
    doc.refresh_from_db()
    assert doc.correspondent == corr
    assert {t.name for t in doc.tags.all()} == set()

from documents.models import Correspondent
from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document


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

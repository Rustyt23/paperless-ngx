import datetime

from documents.models import Document, Correspondent
from documents.signals.handlers import rename_document_by_vendor_and_date


def test_rename_documents_same_vendor_numbered(tmp_path, settings):
    settings.ORIGINALS_DIR = tmp_path
    corr = Correspondent.objects.create(name="Acme Corp")
    added = datetime.datetime(2024, 9, 11, tzinfo=datetime.timezone.utc)

    doc1 = Document.objects.create(
        correspondent=corr,
        checksum="0" * 32,
        mime_type="application/pdf",
        filename="orig1.pdf",
        original_filename="orig1.pdf",
        content="",
        added=added,
    )
    (tmp_path / "orig1.pdf").write_text("test")
    rename_document_by_vendor_and_date(sender=None, document=doc1)
    assert doc1.filename == "Acme_Corp_2024-09-11.pdf"
    assert (tmp_path / doc1.filename).exists()

    doc2 = Document.objects.create(
        correspondent=corr,
        checksum="1" * 32,
        mime_type="application/pdf",
        filename="orig2.pdf",
        original_filename="orig2.pdf",
        content="",
        added=added,
    )
    (tmp_path / "orig2.pdf").write_text("test")
    rename_document_by_vendor_and_date(sender=None, document=doc2)
    assert doc2.filename == "Acme_Corp_2024-09-11_1.pdf"
    assert (tmp_path / doc2.filename).exists()

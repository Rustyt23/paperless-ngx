from PIL import Image

from documents.models import Document, Note
from documents.utils.ocr import ocr_page, process_document_images


class Engine:
    def __init__(self, mapping):
        self.mapping = mapping

    def image_to_string(self, img):
        angle = img.info.get("rotation", 0)
        return self.mapping.get(angle, "")


def test_rotation_selects_best(db):
    engine = Engine({0: "hello", 90: "x" * 180})
    img = Image.new("RGB", (10, 10), "white")
    result = ocr_page(img, ocr_engine=engine)
    assert result["rotation"] == 90
    assert result["char_count"] == 180
    doc = Document.objects.create(checksum="r" * 32, mime_type="application/pdf", content="")
    process_document_images(doc, [img], ocr_engine=engine)
    doc.refresh_from_db()
    assert doc.page_count == 1
    assert Note.objects.filter(document=doc, note="auto-rotated page 1: 90°").exists()


def test_blank_page_removed(db):
    engine = Engine({0: "", 90: "", 180: "", 270: ""})
    img = Image.new("L", (50, 50), "white")
    img.putpixel((0, 0), 0)
    doc = Document.objects.create(checksum="s" * 32, mime_type="application/pdf", content="")
    process_document_images(doc, [img], ocr_engine=engine)
    doc.refresh_from_db()
    assert doc.page_count == 0
    assert Note.objects.filter(document=doc, note="removed blank page 1").exists()


def test_all_blank_document_tagged(db):
    engine = Engine({0: "", 90: "", 180: "", 270: ""})
    img = Image.new("L", (50, 50), "white")
    doc = Document.objects.create(checksum="t" * 32, mime_type="application/pdf", content="")
    process_document_images(doc, [img, img.copy()], ocr_engine=engine)
    doc.refresh_from_db()
    assert doc.page_count == 0
    assert {t.name for t in doc.tags.all()} == {"blank-document"}
    assert doc.correspondent is None

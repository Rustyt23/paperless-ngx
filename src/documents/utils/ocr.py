from __future__ import annotations

from typing import Iterable, Tuple

from PIL import Image

from documents.models import Document, Note, Tag

BLANK_DOCUMENT_TAG = "blank-document"


def _pytesseract():  # pragma: no cover - replaced in tests
    import pytesseract
    return pytesseract


def _ink_coverage(image: Image.Image) -> float:
    gray = image.convert("L").resize((50, 50))
    pixels = list(gray.getdata())
    nonwhite = sum(1 for p in pixels if p < 250)
    return nonwhite / len(pixels)


def ocr_page(image: Image.Image, ocr_engine=None) -> dict:
    engine = ocr_engine or _pytesseract()
    results: list[Tuple[int, str, int, int]] = []
    for angle in (0, 90, 180, 270):
        rotated = image.rotate(angle, expand=True)
        rotated.info["rotation"] = angle
        try:
            text = engine.image_to_string(rotated)
        except Exception:
            text = ""
        char_count = len(text)
        word_count = len(text.split())
        results.append((angle, text, char_count, word_count))
    results.sort(key=lambda x: x[2], reverse=True)
    best = results[0]
    second = results[1] if len(results) > 1 else (0, "", 0, 0)
    if best[2] >= 60 or (second[2] == 0 and best[2] > 0) or best[2] >= second[2] * 1.3:
        chosen = best
    else:
        chosen = results[0]
    ink = _ink_coverage(image)
    is_blank = chosen[2] < 25 and chosen[3] < 8 and ink < 0.005
    return {
        "rotation": chosen[0],
        "text": chosen[1],
        "char_count": chosen[2],
        "word_count": chosen[3],
        "ink": ink,
        "is_blank": is_blank,
    }


def process_document_images(
    document: Document, images: Iterable[Image.Image], ocr_engine=None
) -> None:
    texts: list[str] = []
    kept = 0
    removed_pages: list[int] = []
    for idx, img in enumerate(images, start=1):
        result = ocr_page(img, ocr_engine=ocr_engine)
        if result["is_blank"]:
            removed_pages.append(idx)
            Note.objects.create(document=document, note=f"removed blank page {idx}")
            continue
        kept += 1
        texts.append(result["text"])
        if result["rotation"] != 0:
            Note.objects.create(
                document=document,
                note=f"auto-rotated page {idx}: {result['rotation']}°",
            )
    document.page_count = kept
    document.content = "\n".join(texts)
    document.save(update_fields=["page_count", "content"])
    if kept == 0:
        tag, _ = Tag.objects.get_or_create(name=BLANK_DOCUMENT_TAG)
        document.tags.add(tag)
    # Notes already recorded for removed pages

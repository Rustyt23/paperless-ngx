from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path  # noqa: TC003

from documents.utils import run_subprocess


@dataclass
class OCRStats:
    word_count: int
    char_count: int
    has_text_layer: bool


def get_ocr_stats(source_path: Path, content: str | None) -> tuple[OCRStats, OCRStats]:
    """Return OCR statistics for the first page and overall document.

    Args:
        source_path: Path to the original PDF file.
        content: OCR text for the entire document.
    """
    first = OCRStats(word_count=0, char_count=0, has_text_layer=False)
    if source_path and source_path.is_file():
        try:
            proc = run_subprocess(
                [
                    "pdftotext",
                    "-f",
                    "1",
                    "-l",
                    "1",
                    str(source_path),
                    "-",
                ],
                check_exit_code=False,
                log_stdout=False,
                log_stderr=False,
            )
            text = proc.stdout.decode("utf-8", errors="ignore")
            first = OCRStats(
                word_count=len(text.split()),
                char_count=len(text),
                has_text_layer=bool(text.strip()),
            )
        except Exception:
            first = OCRStats(
                word_count=0,
                char_count=0,
                has_text_layer=False,
            )
    overall_content = content or ""
    overall = OCRStats(
        word_count=len(overall_content.split()),
        char_count=len(overall_content),
        has_text_layer=bool(overall_content.strip()),
    )
    return first, overall

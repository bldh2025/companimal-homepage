#!/usr/bin/env python3
"""Validate the six non-live Korean brochure design prototypes."""

from __future__ import annotations

import json
from pathlib import Path

import fitz
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf" / "concepts"
MANIFEST = ROOT / "output" / "pdf" / "brochure-files.json"
EXPECTED = {
    "company-option-a-homepage-editorial-ko-2026.pdf",
    "company-option-b-sales-proof-ko-2026.pdf",
    "company-option-c-brand-storybook-ko-2026.pdf",
    "product-option-a-visual-catalog-ko-2026.pdf",
    "product-option-b-buyer-specbook-ko-2026.pdf",
    "product-option-c-ingredient-story-ko-2026.pdf",
}


def validate(path: Path) -> dict[str, object]:
    if path.stat().st_size < 100_000:
        raise AssertionError(f"Unexpectedly small prototype: {path}")

    reader = PdfReader(str(path))
    if len(reader.pages) != 4:
        raise AssertionError(f"Expected 4 pages: {path}")
    root = reader.trailer["/Root"]
    if str(root.get("/Lang")) != "ko-KR":
        raise AssertionError(f"Missing ko-KR language metadata: {path}")
    if "/OpenAction" in root or "/AA" in root:
        raise AssertionError(f"Active document action found: {path}")
    names = root.get("/Names")
    if names:
        names = names.get_object()
        if "/JavaScript" in names or "/EmbeddedFiles" in names:
            raise AssertionError(f"JavaScript or attachment found: {path}")

    document = fitz.open(path)
    text_chars = 0
    image_pages = 0
    font_xrefs: set[int] = set()
    for page_no, page in enumerate(document, start=1):
        if (round(page.rect.width), round(page.rect.height)) != (842, 595):
            raise AssertionError(f"Unexpected page geometry on {path}, page {page_no}")
        text = page.get_text("text").strip()
        if len(text) < 40:
            raise AssertionError(f"Searchable text is too sparse on {path}, page {page_no}")
        text_chars += len(text)
        image_pages += bool(page.get_images(full=True))
        font_xrefs.update(font[0] for font in page.get_fonts(full=True))
    if image_pages < 2:
        raise AssertionError(f"Prototype does not demonstrate enough image-led pages: {path}")
    for xref in font_xrefs:
        if not document.extract_font(xref)[3]:
            raise AssertionError(f"Unembedded font in {path}: xref {xref}")
    document.close()
    return {
        "pages": 4,
        "bytes": path.stat().st_size,
        "text_chars": text_chars,
        "image_pages": image_pages,
        "fonts": len(font_xrefs),
    }


def main() -> None:
    actual = {path.name for path in OUTPUT.glob("*.pdf")}
    if actual != EXPECTED:
        raise AssertionError(f"Prototype set mismatch: expected {sorted(EXPECTED)}, got {sorted(actual)}")
    manifest_text = MANIFEST.read_text(encoding="utf-8")
    if "output/pdf/concepts" in manifest_text:
        raise AssertionError("Design prototypes must not be linked from the live download manifest")
    report = {name: validate(OUTPUT / name) for name in sorted(EXPECTED)}
    print(json.dumps({"status": "ok", "prototypes": report}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

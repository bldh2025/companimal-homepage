#!/usr/bin/env python3
"""Validate generated brochure files and the static download integration."""

from __future__ import annotations

import json
from pathlib import Path

import fitz
from pypdf import PdfReader

from brochure_content import LANGUAGES


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf"
MANIFEST_PATH = OUTPUT / "brochure-files.json"
HTML_FILES = [ROOT / "index.html", ROOT / "en" / "index.html", ROOT / "zh" / "index.html", ROOT / "zh-hant" / "index.html"]


def fail(message: str) -> None:
    raise AssertionError(message)


def validate_pdf(path: Path, locale: str, pages: int) -> dict[str, object]:
    if not path.is_file() or path.stat().st_size < 100_000:
        fail(f"Missing or unexpectedly small PDF: {path}")

    reader = PdfReader(str(path))
    if len(reader.pages) != pages:
        fail(f"Unexpected page count for {path}: {len(reader.pages)}")
    if str(reader.trailer["/Root"].get("/Lang")) != locale:
        fail(f"Missing or incorrect /Lang for {path}")
    if not (reader.metadata and reader.metadata.title):
        fail(f"Missing title metadata for {path}")
    root = reader.trailer["/Root"]
    if "/OpenAction" in root or "/AA" in root:
        fail(f"Active PDF action found in {path}")
    names = root.get("/Names")
    if names:
        names = names.get_object()
        if "/JavaScript" in names or "/EmbeddedFiles" in names:
            fail(f"JavaScript or attachment found in {path}")

    document = fitz.open(path)
    page_text = [page.get_text("text").strip() for page in document]
    if any(len(text) < 20 for text in page_text):
        fail(f"Searchable text is missing on one or more pages in {path}")
    combined = "\n".join(page_text)
    for forbidden in ("0000.com", "010-6532-4544"):
        if forbidden in combined:
            fail(f"Legacy placeholder contact found in {path}: {forbidden}")
    font_xrefs = {font[0] for page in document for font in page.get_fonts(full=True)}
    if not font_xrefs:
        fail(f"No fonts found in {path}")
    for xref in font_xrefs:
        extracted = document.extract_font(xref)
        if len(extracted[3]) == 0:
            fail(f"Unembedded font in {path}: xref {xref}")
    document.close()
    return {"pages": pages, "bytes": path.stat().st_size, "text_chars": sum(map(len, page_text)), "fonts": len(font_xrefs)}


def validate_site(manifest: dict[str, object]) -> None:
    expected_fallbacks = ("/output/pdf/company-profile-ko.pdf", "/output/pdf/product-brochure-ko.pdf")
    for path in HTML_FILES:
        source = path.read_text(encoding="utf-8")
        if source.count('id="downloads"') != 1:
            fail(f"Download section missing or duplicated in {path}")
        if source.count('data-brochure-kind="company"') != 1 or source.count('data-brochure-kind="product"') != 1:
            fail(f"Download cards missing or duplicated in {path}")
        if source.count('<script src="/brochure-downloads.js" defer></script>') != 1:
            fail(f"Download script missing or duplicated in {path}")
        if 'href="#downloads"' not in source:
            fail(f"Download navigation link missing in {path}")
        for fallback in expected_fallbacks:
            if fallback not in source:
                fail(f"Fallback PDF link missing in {path}: {fallback}")

    script = (ROOT / "brochure-downloads.js").read_text(encoding="utf-8")
    for code in LANGUAGES:
        if f'"{code}"' not in script:
            fail(f"Language missing from download script: {code}")
    for entry in manifest.values():
        for kind in ("company", "product"):
            if not (ROOT / entry[kind]["path"]).is_file():
                fail(f"Manifest points to a missing file: {entry[kind]['path']}")


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if list(manifest) != list(LANGUAGES):
        fail(f"Manifest languages differ: {list(manifest)}")
    pdfs = sorted(OUTPUT.glob("*.pdf"))
    if len(pdfs) != 14:
        fail(f"Expected exactly 14 PDFs, found {len(pdfs)}")

    report = {}
    for code, language in LANGUAGES.items():
        entry = manifest[code]
        if entry["locale"] != language["locale"]:
            fail(f"Manifest locale mismatch for {code}")
        report[code] = {}
        for kind, expected_pages in (("company", 8), ("product", 10)):
            path = ROOT / entry[kind]["path"]
            report[code][kind] = validate_pdf(path, language["locale"], expected_pages)
            if entry[kind]["bytes"] != path.stat().st_size:
                fail(f"Manifest file size mismatch for {path}")
            if entry[kind]["pages"] != expected_pages:
                fail(f"Manifest page count mismatch for {path}")

    validate_site(manifest)
    print(json.dumps({"status": "ok", "languages": len(manifest), "pdfs": len(pdfs), "details": report}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

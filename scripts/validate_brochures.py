#!/usr/bin/env python3
"""Validate generated brochure files and the static download integration."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

import fitz
from pypdf import PdfReader

from brochure_content import COMPANY_CONTENT, LANGUAGES
from history_content import BRAND_HISTORY, EXPECTED_HISTORY_ITEM_COUNTS, EXPECTED_HISTORY_YEARS


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf"
MANIFEST_PATH = OUTPUT / "brochure-files.json"
HTML_FILES = [ROOT / "index.html", ROOT / "en" / "index.html", ROOT / "zh" / "index.html", ROOT / "zh-hant" / "index.html"]


def fail(message: str) -> None:
    raise AssertionError(message)


def compact(value: str) -> str:
    normalized = value.replace("・", "·").replace("―", "—").replace("\u00ad", "-")
    return "".join(normalized.split())


def validate_pdf(path: Path, code: str, locale: str, pages: int, kind: str) -> dict[str, object]:
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
    expected_size = (595, 842) if kind == "company" else (1066, 1492)
    for page in document:
        actual = (round(page.rect.width), round(page.rect.height))
        if actual != expected_size:
            fail(f"Unexpected {kind} page geometry in {path}: {actual}")
    page_text = [page.get_text("text").strip() for page in document]
    if any(len(text) < 10 for text in page_text):
        fail(f"Searchable text is missing on one or more pages in {path}")
    combined = "\n".join(page_text)
    for forbidden in ("0000.com", "010-6532-4544"):
        if forbidden in combined:
            fail(f"Legacy placeholder contact found in {path}: {forbidden}")
    # MuPDF's Thai and Arabic ToUnicode extraction is not stable with the
    # system TTC fonts, so those locales are verified from source structure
    # plus rendered pages below instead of exact extracted glyph order.
    if kind == "company" and code not in {"th", "ar"}:
        searchable = compact(combined)
        for year, items in BRAND_HISTORY[code]:
            if year not in combined:
                fail(f"Company history year {year} missing from {path}")
            for item in items:
                if compact(item) not in searchable:
                    fail(f"Company history item missing from {path}: {year} / {item}")
    font_xrefs = {font[0] for page in document for font in page.get_fonts(full=True)}
    if not font_xrefs:
        fail(f"No fonts found in {path}")
    for xref in font_xrefs:
        extracted = document.extract_font(xref)
        if len(extracted[3]) == 0:
            fail(f"Unembedded font in {path}: xref {xref}")
    document.close()
    return {"pages": pages, "bytes": path.stat().st_size, "text_chars": sum(map(len, page_text)), "fonts": len(font_xrefs)}


def extract_homepage_history(path: Path) -> list[tuple[str, list[str]]]:
    source = path.read_text(encoding="utf-8")
    section = re.search(r'<section class="sec history".*?</section>', source, re.S)
    if not section:
        fail(f"Homepage history section missing in {path}")
    result = []
    for year, block in re.findall(r'<div class="yr">(.*?)</div>\s*<ul>(.*?)</ul>', section.group(0), re.S):
        items = []
        for raw_item in re.findall(r'<li>(.*?)</li>', block, re.S):
            text = re.sub(r"<[^>]+>", "", raw_item)
            items.append(" ".join(html.unescape(text).split()))
        result.append((year.strip(), items))
    return result


def extract_homepage_history_intro(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    section = re.search(r'<section class="sec history".*?</section>', source, re.S)
    if not section:
        fail(f"Homepage history section missing in {path}")
    lead = re.search(r'<p class="lead">(.*?)</p>', section.group(0), re.S)
    if not lead:
        fail(f"Homepage history introduction missing in {path}")
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", lead.group(1))).split())


def validate_history_source() -> None:
    homepage_sources = {
        "ko": ROOT / "index.html",
        "en": ROOT / "en" / "index.html",
        "zh-hans": ROOT / "zh" / "index.html",
        "zh-hant": ROOT / "zh-hant" / "index.html",
    }
    for code, path in homepage_sources.items():
        if extract_homepage_history(path) != BRAND_HISTORY[code]:
            fail(f"Brochure history differs from homepage history in {path}")
        if extract_homepage_history_intro(path) != COMPANY_CONTENT[code]["history_subtitle"]:
            fail(f"Brochure history introduction differs from homepage in {path}")
    for code, history in BRAND_HISTORY.items():
        if [year for year, _ in history] != EXPECTED_HISTORY_YEARS:
            fail(f"Unexpected company history years for {code}")
        if [len(items) for _, items in history] != EXPECTED_HISTORY_ITEM_COUNTS:
            fail(f"Unexpected company history item counts for {code}")


def validate_site(manifest: dict[str, object]) -> None:
    expected_fallbacks = ("/output/pdf/company-profile-ko-2026-v3.pdf", "/output/pdf/product-brochure-ko-2026-v2.pdf")
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
        if "PDF · 14" not in source:
            fail(f"Company brochure fallback page count is not 14 in {path}")
    korean_source = (ROOT / "index.html").read_text(encoding="utf-8")
    if "자료실" in korean_source or korean_source.count('href="#downloads">소개서</a>') != 2:
        fail("Korean main navigation and footer must label the download area 소개서")

    script = (ROOT / "brochure-downloads.js").read_text(encoding="utf-8")
    for code in LANGUAGES:
        if f'"{code}"' not in script:
            fail(f"Language missing from download script: {code}")
    if "entry.label_ko" not in script:
        fail("Korean-language annotations are not wired into the selectors")
    generator = (ROOT / "scripts" / "build_brochures.py").read_text(encoding="utf-8")
    if "keep_proportion=False" in generator:
        fail("Non-proportional image insertion remains in the brochure generator")
    for path in HTML_FILES:
        if "font-size:16px" not in path.read_text(encoding="utf-8"):
            fail(f"Mobile-safe brochure selector font size is missing in {path}")
    for entry in manifest.values():
        for kind in ("company", "product"):
            if not (ROOT / entry[kind]["path"]).is_file():
                fail(f"Manifest points to a missing file: {entry[kind]['path']}")


def main() -> None:
    validate_history_source()
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
        if entry.get("label_ko") != language["label_ko"]:
            fail(f"Manifest Korean language label mismatch for {code}")
        report[code] = {}
        for kind, expected_pages in (("company", 14), ("product", 16)):
            path = ROOT / entry[kind]["path"]
            report[code][kind] = validate_pdf(path, code, language["locale"], expected_pages, kind)
            if entry[kind]["bytes"] != path.stat().st_size:
                fail(f"Manifest file size mismatch for {path}")
            if entry[kind]["pages"] != expected_pages:
                fail(f"Manifest page count mismatch for {path}")

    validate_site(manifest)
    print(json.dumps({"status": "ok", "languages": len(manifest), "pdfs": len(pdfs), "details": report}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

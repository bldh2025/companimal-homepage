#!/usr/bin/env python3
"""Validate generated brochure files and the static download integration."""

from __future__ import annotations

import html
import hashlib
import json
import re
from pathlib import Path

import fitz
from pypdf import PdfReader

from brochure_content import COMPANY_CONTENT, LANGUAGES, PRODUCT_CONTENT
from build_brochures import CHANNEL_URLS, CONTACT_URIS, HOMEPAGE_COMPANY
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


def rect_touches(rect: fitz.Rect, image_rect: fitz.Rect, tolerance: float = 1.0) -> bool:
    horizontal_overlap = rect.x0 <= image_rect.x1 + tolerance and rect.x1 >= image_rect.x0 - tolerance
    vertical_overlap = rect.y0 <= image_rect.y1 + tolerance and rect.y1 >= image_rect.y0 - tolerance
    return horizontal_overlap and vertical_overlap


def is_image_boundary(drawing: dict[str, object], image_rects: list[fitz.Rect]) -> bool:
    rect = drawing.get("rect")
    if not isinstance(rect, fitz.Rect) or not any(rect_touches(rect, image_rect) for image_rect in image_rects):
        return False
    for opacity_key in ("fill_opacity", "stroke_opacity"):
        opacity = drawing.get(opacity_key)
        if isinstance(opacity, (float, int)) and opacity < 0.999:
            return True
    stroke = drawing.get("color")
    return isinstance(stroke, (tuple, list)) and len(stroke) == 3 and max(stroke) < 0.16


def validate_image_boundary_guard() -> None:
    image_rect = fitz.Rect(20, 20, 80, 80)
    if is_image_boundary({"rect": fitz.Rect(0, 0, 10, 10), "fill_opacity": 0.5}, [image_rect]):
        fail("Boundary guard rejected unrelated transparency")
    if not is_image_boundary({"rect": fitz.Rect(20, 60, 80, 80), "fill_opacity": 0.5}, [image_rect]):
        fail("Boundary guard missed a translucent image overlay")
    if not is_image_boundary({"rect": fitz.Rect(20, 20, 80, 80), "stroke_opacity": 0.5}, [image_rect]):
        fail("Boundary guard missed a translucent image-edge stroke")
    if not is_image_boundary({"rect": fitz.Rect(20, 20, 80, 80), "color": (0.0, 0.0, 0.0)}, [image_rect]):
        fail("Boundary guard missed a dark image-edge stroke")
    if is_image_boundary({"rect": fitz.Rect(20, 20, 80, 80), "color": (0.88, 0.84, 0.74)}, [image_rect]):
        fail("Boundary guard rejected an intended light card border")


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
    expected_size = (842, 595)
    for page in document:
        actual = (round(page.rect.width), round(page.rect.height))
        if actual != expected_size:
            fail(f"Unexpected {kind} page geometry in {path}: {actual}")
        image_rects = [rect for image in page.get_images(full=True) for rect in page.get_image_rects(image[0])]
        for drawing in page.get_drawings():
            if is_image_boundary(drawing, image_rects):
                fail(f"Dark or translucent image boundary found in {path} page {page.number + 1}")
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
        homepage_copy = HOMEPAGE_COMPANY[code]
        required_copy = [
            homepage_copy["ceo"][2],
            homepage_copy["team"][1],
            homepage_copy["team"][2],
            homepage_copy["profile"][1],
            homepage_copy["donation"][1],
            homepage_copy["donation"][3],
        ]
        required_copy.extend(value for _, value, _ in homepage_copy["profile"][3])
        for expected in required_copy:
            if compact(expected) not in searchable:
                fail(f"Homepage company content missing from {path}: {expected}")
    if kind == "company":
        if len(document[1].get_images(full=True)) < 1:
            fail(f"CEO photograph missing from {path}")
        if len(document[2].get_images(full=True)) < 3:
            fail(f"Team or team-tee imagery missing from {path}")
        portfolio_images = document[5].get_image_info()
        if len(portfolio_images) != 8:
            fail(f"Eight-product portfolio imagery missing from {path}")
        for image in portfolio_images:
            bbox = image.get("bbox")
            if bbox is None or abs(fitz.Rect(bbox).width - fitz.Rect(bbox).height) > 0.1:
                fail(f"Product portfolio image is not square in {path}: {bbox}")
        if document[12].get_image_info():
            fail(f"Partnership page still contains a right-side photo in {path}")
        for image in document[13].get_image_info():
            bbox = image.get("bbox")
            if bbox is not None and fitz.Rect(bbox).x0 >= 470:
                fail(f"Contact page still contains a right-side photo in {path}: {bbox}")
        channel_links = {link.get("uri") for link in document[7].get_links() if link.get("uri")}
        if not set(CHANNEL_URLS).issubset(channel_links):
            fail(f"Homepage sales-channel links missing from {path}")
        contact_links = {link.get("uri") for link in document[13].get_links() if link.get("uri")}
        if not {uri for uri in CONTACT_URIS if uri}.issubset(contact_links):
            fail(f"Contact links missing from {path}")
    if kind == "product":
        product_content = PRODUCT_CONTENT[code]
        if "30g" not in compact(combined):
            fail(f"Trial-pack size missing from {path}")
        if len(document[2].get_images(full=True)) < 8:
            fail(f"Eight-product lineup imagery missing from {path}")
        lineup_text = compact(document[2].get_text("text"))
        for forbidden in ("1kg", "350g", "400g", "100g", "240g", "200g", "3종", "4종"):
            if forbidden in lineup_text:
                fail(f"Product lineup contains pack metadata ({forbidden}) in {path}")
        for page_no in range(3, 11):
            detail_images = document[page_no].get_image_info()
            if len(detail_images) != 1 or abs(fitz.Rect(detail_images[0]["bbox"]).width - fitz.Rect(detail_images[0]["bbox"]).height) > 0.1:
                fail(f"Product detail image is not square in {path} page {page_no + 1}")
        trial_images = document[12].get_image_info()
        if len(trial_images) != 4 or any(abs(fitz.Rect(image["bbox"]).width - fitz.Rect(image["bbox"]).height) > 0.1 for image in trial_images):
            fail(f"Trial-pack source images are missing or distorted in {path}")
        comparison_images = document[13].get_image_info()
        if len(comparison_images) != 12 or any(abs(fitz.Rect(image["bbox"]).width - fitz.Rect(image["bbox"]).height) > 0.1 for image in comparison_images):
            fail(f"Buyer-comparison images are missing or distorted in {path}")
        product_links = {link.get("uri") for link in document[14].get_links() if link.get("uri")}
        if not {"https://companimal.kr", "https://pf.kakao.com/_xnyDcs"}.issubset(product_links):
            fail(f"Product contact links missing from {path}")
        if code not in {"th", "ar"}:
            searchable = compact(combined)
            for label in product_content["catalog"][:8]:
                if compact(label) not in searchable:
                    fail(f"Product lineup label missing from {path}: {label}")
            for key, item in product_content["products"].items():
                if compact(item[3]) not in searchable:
                    fail(f"Product pack variant missing from {path}: {key} / {item[3]}")
        if code != "ko" and any(leak in combined for leak in ("바이어용 비교", "제품 · 포장 · 구성", "MOQ · 공급가 · 리드타임")):
            fail(f"Korean buyer-copy leakage found in {path}")
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


def validate_homepage_company_source() -> None:
    source = (ROOT / "index.html").read_text(encoding="utf-8")
    plain = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", source)).split())
    homepage_copy = HOMEPAGE_COMPANY["ko"]
    for expected in (
        homepage_copy["ceo"][2],
        homepage_copy["team"][1],
        homepage_copy["team"][2],
        homepage_copy["donation"][1],
        homepage_copy["donation"][3],
    ):
        if expected not in plain:
            fail(f"Company brochure source differs from Korean homepage: {expected}")
    for asset in ("ceo_jangseonghwan.webp", "team_walk.webp", "tee_black.webp", "tee_white.webp"):
        if asset not in source:
            fail(f"Homepage company asset is missing: {asset}")


def validate_featured_html(entry: dict[str, object]) -> None:
    if entry.get("format") != "html":
        fail("Featured HTML brochure manifest format must be html")
    if entry.get("pages") != 12:
        fail("Featured HTML brochure manifest page count must be 12")
    path = ROOT / str(entry["path"])
    if not path.is_file() or path.is_symlink() or path.stat().st_size < 1_000_000:
        fail(f"Featured HTML brochure is missing or unexpectedly small: {path}")
    if entry.get("bytes") != path.stat().st_size:
        fail(f"Featured HTML byte count mismatch: {path}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if entry.get("sha256") != digest:
        fail(f"Featured HTML SHA-256 mismatch: {path}")
    source = path.read_text(encoding="utf-8")
    manifest_match = re.search(r'<script type="__bundler/manifest">(.*?)</script>', source, re.S)
    template_match = re.search(r'<script type="__bundler/template">(.*?)</script>', source, re.S)
    if not manifest_match or not template_match:
        fail(f"Featured HTML bundler manifest/template missing: {path}")
    try:
        bundled_manifest = json.loads(manifest_match.group(1))
        template = json.loads(template_match.group(1))
    except json.JSONDecodeError as error:
        fail(f"Featured HTML bundle JSON is invalid: {path}: {error}")
    if len(re.findall(r"<section\b", template, re.I)) != 12:
        fail(f"Featured HTML slide count is not 12: {path}")
    references = set(re.findall(r"\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b", template, re.I))
    if not references.issubset(bundled_manifest):
        fail(f"Featured HTML has missing bundled asset references: {path}")
    for required in ("ZERO LABS", "주식회사 반려동행", "Remove", "Balance", "Supply"):
        if required not in template:
            fail(f"Featured HTML required content missing: {required}")


def validate_product_html(entry: dict[str, object]) -> None:
    if entry.get("format") != "html" or entry.get("pages") != 16:
        fail("Featured product HTML manifest metadata is invalid")
    path = ROOT / str(entry["path"])
    if not path.is_file() or path.is_symlink():
        fail(f"Featured product HTML is missing: {path}")
    data = path.read_bytes()
    if entry.get("bytes") != len(data) or entry.get("sha256") != hashlib.sha256(data).hexdigest():
        fail(f"Featured product HTML hash or byte count mismatch: {path}")
    source = data.decode("utf-8")
    if source.count('<section class="') != 16 or 'class="product-detail"' not in source:
        fail(f"Featured product HTML section structure is invalid: {path}")
    for required in ("고기가득", "영양가득", "베리가득", "치카하개", "굽빵", "미트리스", "멍스", "프레쉬링"):
        if required not in source:
            fail(f"Featured product HTML content missing: {required}")


def validate_site(manifest: dict[str, object]) -> None:
    for path in HTML_FILES:
        source = path.read_text(encoding="utf-8")
        if source.count('id="downloads"') != 1:
            fail(f"Download section missing or duplicated in {path}")
        if source.count('data-brochure-kind="company"') != 1 or source.count('data-brochure-kind="product"') != 1:
            fail(f"Download cards missing or duplicated in {path}")
        if len(re.findall(r'<script src="/brochure-downloads\.js(?:\?[^\"]*)?" defer></script>', source)) != 1:
            fail(f"Download script missing or duplicated in {path}")
        if 'href="#downloads"' not in source:
            fail(f"Download navigation link missing in {path}")
        expected_fallbacks = ("/output/brochure/zerolabs-company-profile-ko-2026.html", "/output/brochure/zerolabs-product-profile-ko-2026.html") if path == ROOT / "index.html" else ("/output/pdf/company-profile-ko-2026-v6.pdf", "/output/pdf/product-brochure-ko-2026-v3.pdf")
        for fallback in expected_fallbacks:
            if fallback not in source:
                fail(f"Fallback PDF link missing in {path}: {fallback}")
        if path == ROOT / "index.html" and ("type=\"text/html\"" not in source or "HTML · 12쪽" not in source):
            fail(f"Korean featured HTML fallback is not wired in {path}")
        if path == ROOT / "index.html" and source.count('type="text/html"') < 2:
            fail(f"Korean product HTML fallback is not wired in {path}")
        if path != ROOT / "index.html" and "PDF · 14" not in source:
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
    styles = (ROOT / "styles.css").read_text(encoding="utf-8")
    if not re.search(r"\.download-select\{[^}]*font-size:16px", styles):
        fail("Mobile-safe brochure selector font size is missing in styles.css")
    for entry in manifest.values():
        for kind in ("company", "product"):
            if not (ROOT / entry[kind]["path"]).is_file():
                fail(f"Manifest points to a missing file: {entry[kind]['path']}")
    if "companyHtml" not in manifest["ko"]:
        fail("Korean featured HTML brochure is missing from the manifest")
    validate_featured_html(manifest["ko"]["companyHtml"])
    if "productHtml" not in manifest["ko"]:
        fail("Korean featured product HTML brochure is missing from the manifest")
    validate_product_html(manifest["ko"]["productHtml"])


def main() -> None:
    validate_image_boundary_guard()
    validate_history_source()
    validate_homepage_company_source()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if list(manifest) != list(LANGUAGES):
        fail(f"Manifest languages differ: {list(manifest)}")
    pdfs = sorted(
        {
            ROOT / entry[kind]["path"]
            for entry in manifest.values()
            for kind in ("company", "product")
        }
    )
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
        for kind, expected_pages in (("company", 14), ("product", 15)):
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

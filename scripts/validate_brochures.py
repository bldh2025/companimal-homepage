#!/usr/bin/env python3
"""Validate generated brochure files and the static download integration."""

from __future__ import annotations

import base64
import html
import hashlib
import io
import json
import re
import unicodedata
from pathlib import Path

import fitz
from PIL import Image
from pypdf import PdfReader

from brochure_content import COMPANY_CONTENT, LANGUAGES, PRODUCT_CONTENT
from build_brochures import (
    CHANNEL_URLS,
    COMPANY_REVIEW_PORTFOLIO_KEYS,
    COMPANY_PAGE_COUNT,
    CONTACT_URIS,
    HOMEPAGE_COMPANY,
    PRODUCT_PAGE_COUNT,
    PRODUCT_REVIEW_AS_OF,
    PRODUCT_REVIEW_COUNTS,
    PRODUCT_REVIEW_DEFINITION,
    PRODUCT_REVIEW_LINEUP_KEYS,
    PRODUCT_REVIEW_SNAPSHOT,
    PRODUCT_REVIEW_TOTAL,
    REVIEW_UI,
    WHOLESALE_URL,
)
from history_content import BRAND_HISTORY, EXPECTED_HISTORY_ITEM_COUNTS, EXPECTED_HISTORY_YEARS
from embed_company_profile_factory_images import (
    CARD_DISCLOSURE,
    FACTORY_IMAGE_SPECS,
    MAX_FACTORY_IMAGE_BYTES,
    PROVENANCE_PATH,
    SECTION_DISCLOSURE,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf"
MANIFEST_PATH = OUTPUT / "brochure-files.json"
HTML_FILES = [ROOT / "index.html", ROOT / "en" / "index.html", ROOT / "zh" / "index.html", ROOT / "zh-hant" / "index.html"]
EXPECTED_EMAIL = "ceo@companimal.kr"
LEGACY_EMAIL = "bldh2025@naver.com"
LATEST_COMPANY_HTML = "output/brochure/zerolabs-company-profile-ko-2026.html"
LEGACY_COMPANY_PDF_PATTERN = "company-profile-*-2026-v6.pdf"
LEGACY_COMPANY_PREVIEW = OUTPUT / "company-profile-preview-ko.png"
LEGACY_PRODUCT_HTML = ROOT / "output" / "brochure" / "zerolabs-product-profile-ko-2026.html"

EXPECTED_PRODUCT_REVIEW_COUNTS = {
    "meat": 11_659,
    "nutrition": 6_473,
    "berry": 10_906,
    "dental": 1_886,
    "baked": 54,
    "meatless": 433,
    "mungs": 477,
    "fresh": 869,
}
EXPECTED_COMPANY_REVIEW_PORTFOLIO_KEYS = (
    "meat",
    "nutrition",
    "berry",
    "dental",
    "baked",
    "meatless",
    "mungs",
    "fresh",
)
EXPECTED_REVIEW_DEFINITION = "2026.08.27 기준 · 회사 제공 판매채널 화면의 공개 리뷰 게시물 수 합산 · 포장 규격을 통합한 제품군 기준"
EXPECTED_REVIEW_LABELS = {
    "meat": "고기가득",
    "nutrition": "영양가득",
    "berry": "베리가득",
    "dental": "치카하개",
    "baked": "굽빵",
    "meatless": "미트리스",
    "mungs": "멍스",
    "fresh": "프레쉬링",
}


def fail(message: str) -> None:
    raise AssertionError(message)


def compact(value: str) -> str:
    normalized = value.replace("・", "·").replace("―", "—").replace("\u00ad", "-").replace("\u200b", "").replace("\x00", "")
    normalized = unicodedata.normalize("NFKC", normalized)
    # MuPDF may extract a middle dot as NUL in Arabic runs. It is a visual
    # separator rather than semantic content, so remove it on both sides.
    normalized = normalized.replace("·", "")
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


def validate_review_snapshot_source() -> None:
    if PRODUCT_REVIEW_COUNTS != EXPECTED_PRODUCT_REVIEW_COUNTS:
        fail(f"Product review snapshot differs from the approved source: {PRODUCT_REVIEW_COUNTS}")
    if PRODUCT_REVIEW_TOTAL != 32_757 or PRODUCT_REVIEW_TOTAL != sum(PRODUCT_REVIEW_COUNTS.values()):
        fail(f"Product review total is inconsistent: {PRODUCT_REVIEW_TOTAL}")
    if PRODUCT_REVIEW_AS_OF != "2026.08.27":
        fail(f"Product review snapshot date is inconsistent: {PRODUCT_REVIEW_AS_OF}")
    if PRODUCT_REVIEW_SNAPSHOT.get("asOfIso") != "2026-08-27":
        fail(f"Product review ISO date is inconsistent: {PRODUCT_REVIEW_SNAPSHOT.get('asOfIso')}")
    if PRODUCT_REVIEW_SNAPSHOT.get("definition") != EXPECTED_REVIEW_DEFINITION:
        fail("Product review definition is not the approved narrow disclosure")
    labels = {
        key: value.get("label")
        for key, value in PRODUCT_REVIEW_SNAPSHOT.get("products", {}).items()
    }
    if labels != EXPECTED_REVIEW_LABELS:
        fail(f"Product review labels differ from the approved mapping: {labels}")
    if COMPANY_REVIEW_PORTFOLIO_KEYS != EXPECTED_COMPANY_REVIEW_PORTFOLIO_KEYS:
        fail(f"Company review portfolio order is inconsistent: {COMPANY_REVIEW_PORTFOLIO_KEYS}")


def review_copy(code: str, field: str, *, count: int | None = None) -> str:
    return REVIEW_UI[code][field].format(
        total=f"{PRODUCT_REVIEW_TOTAL:,}",
        count=f"{count:,}" if count is not None else "",
        date=PRODUCT_REVIEW_AS_OF,
    )


def validate_review_page(document: fitz.Document, code: str, path: Path, kind: str) -> None:
    page = document[5] if kind == "company" else document[2]
    page_text = compact(page.get_text("text"))
    for field in ("summary", "source"):
        if compact(review_copy(code, field)) not in page_text:
            fail(f"Localized review {field} copy missing from {kind} review page in {path}")

    rtl = LANGUAGES[code]["dir"] == "rtl"
    if kind == "company":
        localized_names = {
            key: item[0]
            for key, item in zip(COMPANY_REVIEW_PORTFOLIO_KEYS, COMPANY_CONTENT[code]["products"])
        }
        visual_keys = list(COMPANY_REVIEW_PORTFOLIO_KEYS)
        if rtl:
            visual_keys = [visual_keys[index] for index in (3, 2, 1, 0, 7, 6, 5, 4)]
        cards = []
        for visual_index, review_key in enumerate(visual_keys):
            row, col = divmod(visual_index, 4)
            x, y = 48 + col * 187, 150 + row * 188
            cards.append((review_key, localized_names[review_key], fitz.Rect(x, y, x + 169, y + 185)))
    else:
        cards = []
        for semantic_index, (product_key, review_key) in enumerate(PRODUCT_REVIEW_LINEUP_KEYS):
            row, col = divmod(semantic_index, 4)
            visual_col = 3 - col if rtl else col
            x, y = 48 + visual_col * 187, 140 + row * 188
            name = PRODUCT_CONTENT[code]["products"][product_key][0]
            cards.append((review_key, name, fitz.Rect(x, y, x + 169, y + 173)))

    for review_key, expected_name, card in cards:
        card_text = compact(page.get_textbox(card))
        expected_count = f"{PRODUCT_REVIEW_COUNTS[review_key]:,}"
        if compact(expected_name) not in card_text or expected_count not in card_text:
            fail(
                f"Review card mapping mismatch for {review_key} in {path}: "
                f"expected {expected_name!r} with {expected_count}"
            )


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
    for forbidden in ("0000.com", "010-6532-4544", LEGACY_EMAIL):
        if forbidden in combined:
            fail(f"Legacy placeholder contact found in {path}: {forbidden}")
    if EXPECTED_EMAIL not in combined:
        fail(f"Current contact email missing from {path}: {EXPECTED_EMAIL}")
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
        validate_review_page(document, code, path, kind)
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
        validate_review_page(document, code, path, kind)
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
        if not {"https://companimal.kr", "https://pf.kakao.com/_xnyDcs", WHOLESALE_URL, f"mailto:{EXPECTED_EMAIL}"}.issubset(product_links):
            fail(f"Product contact links missing from {path}")
        if "제로랩스.com" not in combined:
            fail(f"Product wholesale address missing from {path}")
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
    if entry.get("pages") != 13:
        fail("Featured HTML brochure manifest page count must be 13")
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
        fail(f"Featured HTML base slide count is not 12: {path}")
    references = set(re.findall(r"\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b", template, re.I))
    if not references.issubset(bundled_manifest):
        fail(f"Featured HTML has missing bundled asset references: {path}")
    if (
        template.count(SECTION_DISCLOSURE) != 1
        or template.count(f">{CARD_DISCLOSURE}</span>") != len(FACTORY_IMAGE_SPECS)
        or template.count(
            f'data-ai-image-disclosure="production-reference-images" '
            f'style="margin:0; font-size:19px; line-height:1.45; '
            f'color:#4c5c50; flex:none;"'
        )
        != 1
    ):
        fail("Featured company AI reference image disclosure is missing or duplicated")
    try:
        provenance = json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"Featured company AI image provenance is invalid: {error}")
    provenance_assets = {item.get("path"): item for item in provenance.get("assets", [])}
    if provenance.get("generation_tool") != "Codex built-in imagegen" or provenance.get("disclosure") != SECTION_DISCLOSURE:
        fail("Featured company AI image provenance contract is invalid")
    for asset_id, spec in FACTORY_IMAGE_SPECS.items():
        expected_alt = str(spec["alt"])
        if template.count(f'data-ai-image="{asset_id}"') != 1:
            fail(f"Featured company AI image marker is missing: {asset_id}")
        if template.count(f'data-ai-image-label="{asset_id}"') != 1:
            fail(f"Featured company AI image label is missing: {asset_id}")
        if template.count(f'alt="{expected_alt}"') != 1:
            fail(f"Featured company AI image alt text is invalid: {asset_id}")
        item = bundled_manifest.get(asset_id)
        if not isinstance(item, dict) or item.get("mime") != "image/jpeg" or item.get("compressed") is not False:
            fail(f"Featured company AI image manifest metadata is invalid: {asset_id}")
        try:
            decoded = base64.b64decode(str(item.get("data", "")), validate=True)
        except (ValueError, TypeError) as error:
            fail(f"Featured company AI image payload is invalid: {asset_id}: {error}")
        asset_path = ROOT / str(spec["path"])
        if not asset_path.is_file() or asset_path.is_symlink():
            fail(f"Featured company AI source asset is missing: {asset_path}")
        if decoded != asset_path.read_bytes() or hashlib.sha256(decoded).hexdigest() != spec["sha256"]:
            fail(f"Featured company AI image bytes or SHA-256 differ: {asset_id}")
        provenance_item = provenance_assets.get(str(spec["path"]))
        if not isinstance(provenance_item, dict) or provenance_item.get("derived_jpeg_sha256") != spec["sha256"]:
            fail(f"Featured company AI image provenance differs: {asset_id}")
        if not decoded.startswith(b"\xff\xd8\xff") or len(decoded) > MAX_FACTORY_IMAGE_BYTES:
            fail(f"Featured company AI image format or size is invalid: {asset_id}")
        with Image.open(io.BytesIO(decoded)) as image:
            if image.format != "JPEG" or image.mode != "RGB" or image.size != (1200, 800):
                fail(f"Featured company AI image dimensions or color mode are invalid: {asset_id}")
            if image.getexif().get_ifd(0x8825):
                fail(f"Featured company AI image contains GPS metadata: {asset_id}")
    for required in ("ZERO LABS", "주식회사 반려동행", "Remove", "Balance", "Supply"):
        if required not in template:
            fail(f"Featured HTML required content missing: {required}")
    if EXPECTED_EMAIL not in template or "[ 이메일 입력 ]" in template or "[ 도매몰 주소 입력 ]" in template or LEGACY_EMAIL in template:
        fail(f"Featured company HTML contact email is stale: {path}")
    patch_script = (ROOT / "company-contact-patch.js").read_text(encoding="utf-8")
    if EXPECTED_EMAIL not in patch_script or LEGACY_EMAIL in patch_script:
        fail("Featured company HTML contact patch is stale")
    for required in (
        "enhanceCompanyProfile",
        'data-review-proof',
        "MARKET PROOF",
        "cloneNode(true)",
        'doc.querySelector("x-import")',
        "snapshot.total.toLocaleString",
        "sections.length !== 13",
    ):
        if required not in patch_script:
            fail(f"Featured company review enhancer contract is missing: {required}")
    if EXPECTED_REVIEW_DEFINITION not in (ROOT / "brochure-review-data.js").read_text(encoding="utf-8"):
        fail("Canonical review disclosure is missing from browser data")
    if PRODUCT_REVIEW_DEFINITION != EXPECTED_REVIEW_DEFINITION:
        fail("Brochure builder review disclosure is not canonical")
    if source.count('../../brochure-review-data.js') != 1 or source.count('../../company-contact-patch.js') != 1:
        fail("Featured company review scripts are missing or duplicated")
    hook = source.find("window.enhanceCompanyProfile(doc)")
    parsed = source.find("new DOMParser().parseFromString(template, 'text/html')")
    swapped = source.find("document.documentElement.replaceWith(doc.documentElement)")
    if not (0 <= parsed < hook < swapped):
        fail("Featured company review enhancer is not between parse and root swap")
    if "doc = new DOMParser().parseFromString(template, 'text/html');" not in source or "catch (enhancementError)" not in source:
        fail("Featured company review enhancer does not fail open to the base deck")


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
    page_numbers = re.findall(r'class="page">(\d{2} / \d{2})</span>', source)
    if page_numbers != [f"{page:02d} / 16" for page in range(2, 17)]:
        fail(f"Featured product HTML page numbers are inconsistent: {page_numbers}")
    eyebrow_numbers = [
        int(value)
        for value in re.findall(r'class="eyebrow">(\d{2}) — ', source)
    ]
    if eyebrow_numbers != list(range(1, 16)):
        fail(f"Featured product HTML section numbers are inconsistent: {eyebrow_numbers}")
    for key in EXPECTED_PRODUCT_REVIEW_COUNTS:
        if source.count(f'data-review-key="{key}"') != 2:
            fail(f"Featured product HTML review mapping is not overview+detail for {key}")
    review_count_targets = len(re.findall(r"\sdata-review-count(?:\s|>)", source))
    if source.count('class="market-response"') != 8 or review_count_targets != 16:
        fail("Featured product HTML review badges are incomplete")
    review_total_targets = len(re.findall(r"\sdata-review-total(?:\s|>)", source))
    review_total_number_targets = len(re.findall(r"\sdata-review-total-number(?:\s|>)", source))
    review_source_targets = len(re.findall(r"\sdata-review-source(?:\s|>)", source))
    if review_total_targets != 2 or review_total_number_targets != 1 or review_source_targets != 1:
        fail("Featured product HTML review summary is incomplete")
    if 'document.querySelectorAll("[data-review-total-number]")' not in source:
        fail("Featured product HTML review title is not bound to canonical data")
    if source.count('../../brochure-review-data.js') != 1 or EXPECTED_REVIEW_DEFINITION not in (ROOT / "brochure-review-data.js").read_text(encoding="utf-8"):
        fail("Featured product HTML canonical review data is not wired once")
    if EXPECTED_EMAIL not in source or f"mailto:{EXPECTED_EMAIL}" not in source or "제로랩스.com" not in source or LEGACY_EMAIL in source:
        fail(f"Featured product HTML contact email is stale: {path}")


def validate_site(manifest: dict[str, object]) -> None:
    for path in HTML_FILES:
        source = path.read_text(encoding="utf-8")
        if EXPECTED_EMAIL not in source or f"mailto:{EXPECTED_EMAIL}" not in source or LEGACY_EMAIL in source:
            fail(f"Homepage contact email is stale: {path}")
        if source.count('id="downloads"') != 1:
            fail(f"Download section missing or duplicated in {path}")
        if source.count('data-brochure-kind="company"') != 1 or source.count('data-brochure-kind="product"') != 1:
            fail(f"Download cards missing or duplicated in {path}")
        if len(re.findall(r'<script src="/brochure-downloads\.js(?:\?[^\"]*)?" defer></script>', source)) != 1:
            fail(f"Download script missing or duplicated in {path}")
        if 'href="#downloads"' not in source:
            fail(f"Download navigation link missing in {path}")
        expected_fallbacks = (f"/{LATEST_COMPANY_HTML}", "/output/brochure/zerolabs-product-profile-ko-2026-v2.html") if path == ROOT / "index.html" else (f"/{LATEST_COMPANY_HTML}", "/output/pdf/product-brochure-ko-2026-v3.pdf")
        for fallback in expected_fallbacks:
            if fallback not in source:
                fail(f"Fallback brochure link missing in {path}: {fallback}")
        if path == ROOT / "index.html" and ("type=\"text/html\"" not in source or "HTML · 13쪽" not in source):
            fail(f"Korean featured HTML fallback is not wired in {path}")
        if path == ROOT / "index.html" and source.count('type="text/html"') < 2:
            fail(f"Korean product HTML fallback is not wired in {path}")
        company_fallback_meta = {
            ROOT / "en" / "index.html": "HTML · 13 pages",
            ROOT / "zh" / "index.html": "HTML · 13页",
            ROOT / "zh-hant" / "index.html": "HTML · 13頁",
        }
        if path in company_fallback_meta and company_fallback_meta[path] not in source:
            fail(f"Latest company HTML fallback metadata is missing in {path}")
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
    if "brochure-files.json.new" in generator or "staged_manifest" in generator:
        fail("The PDF builder must not publish the live brochure manifest")
    styles = (ROOT / "styles.css").read_text(encoding="utf-8")
    if not re.search(r"\.download-select\{[^}]*font-size:16px", styles):
        fail("Mobile-safe brochure selector font size is missing in styles.css")
    for entry in manifest.values():
        for kind in ("companyHtml", "productHtml", "product"):
            artifact = entry.get(kind)
            if artifact and not (ROOT / artifact["path"]).is_file():
                fail(f"Manifest points to a missing file: {artifact['path']}")
        if "company" in entry:
            fail("Legacy company PDF remains in the live manifest")
    if "companyHtml" not in manifest["ko"]:
        fail("Korean featured HTML brochure is missing from the manifest")
    if manifest["ko"]["companyHtml"].get("path") != LATEST_COMPANY_HTML:
        fail("Live company profile does not point to the latest HTML")
    validate_featured_html(manifest["ko"]["companyHtml"])
    if "productHtml" not in manifest["ko"]:
        fail("Korean featured product HTML brochure is missing from the manifest")
    validate_product_html(manifest["ko"]["productHtml"])
    if list(OUTPUT.glob(LEGACY_COMPANY_PDF_PATTERN)):
        fail("Legacy company PDF files remain in the live output directory")
    if LEGACY_COMPANY_PREVIEW.exists():
        fail("Legacy company PDF preview remains in the live output directory")
    if LEGACY_PRODUCT_HTML.exists():
        fail("Superseded product HTML remains beside the v2 live edition")


def main() -> None:
    validate_image_boundary_guard()
    validate_review_snapshot_source()
    validate_history_source()
    validate_homepage_company_source()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if list(manifest) != list(LANGUAGES):
        fail(f"Manifest languages differ: {list(manifest)}")
    pdfs = sorted({ROOT / entry["product"]["path"] for entry in manifest.values()})
    if len(pdfs) != len(LANGUAGES):
        fail(f"Expected exactly {len(LANGUAGES)} product PDFs, found {len(pdfs)}")

    report = {}
    for code, language in LANGUAGES.items():
        entry = manifest[code]
        if entry["locale"] != language["locale"]:
            fail(f"Manifest locale mismatch for {code}")
        if entry.get("label_ko") != language["label_ko"]:
            fail(f"Manifest Korean language label mismatch for {code}")
        report[code] = {}
        for kind, expected_pages in (("product", PRODUCT_PAGE_COUNT),):
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

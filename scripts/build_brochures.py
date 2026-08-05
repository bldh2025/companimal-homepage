#!/usr/bin/env python3
"""Build localized, searchable ZERO LABS PDF brochures.

Outputs are generated from one content source so the website manifest and all
language variants cannot drift independently.
"""

from __future__ import annotations

import argparse
import html
import io
import json
import shutil
from pathlib import Path

import fitz
import qrcode
from PIL import Image
from fontTools.ttLib import TTCollection
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, TextStringObject

from brochure_content import COMPANY_CONTENT, LANGUAGES, PRODUCT_CONTENT


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "zerolabs_homepage_assets"
OUTPUT = ROOT / "output" / "pdf"
TMP = ROOT / "tmp" / "pdfs"
FONT_DIR = TMP / "fonts"
RENDER_DIR = TMP / "rendered"

PAGE = fitz.Rect(0, 0, 595, 842)
FOREST = (22 / 255, 36 / 255, 26 / 255)
GREEN = (31 / 255, 51 / 255, 37 / 255)
MID_GREEN = (44 / 255, 70 / 255, 50 / 255)
CREAM = (245 / 255, 241 / 255, 232 / 255)
CREAM_2 = (236 / 255, 230 / 255, 214 / 255)
GOLD = (216 / 255, 179 / 255, 106 / 255)
WHITE = (1, 1, 1)

CONTACT_VALUES = [
    "https://companimal.kr",
    "https://zerolabs.co.kr",
    "https://제로랩스.com",
    "https://pf.kakao.com/_xnyDcs",
    "bldh2025@naver.com",
    "Unit 215-26, 30 Namdong-seoro 236beon-gil, Namdong-gu, Incheon, Republic of Korea",
]

PRODUCT_CONTACT_VALUES = [
    "https://companimal.kr",
    "https://pf.kakao.com/_xnyDcs",
    "bldh2025@naver.com",
    "Unit 215-26, 30 Namdong-seoro 236beon-gil, Namdong-gu, Incheon, Republic of Korea",
]

FONT_FILES = {
    "en": (Path("/System/Library/Fonts/Supplemental/Arial.ttf"), Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf")),
    "ko": (FONT_DIR / "ko-regular.ttf", FONT_DIR / "ko-bold.ttf"),
    "cjk": (FONT_DIR / "cjk-regular.ttf", FONT_DIR / "cjk-bold.ttf"),
    "th": (FONT_DIR / "th-regular.ttf", FONT_DIR / "th-bold.ttf"),
    "ar": (FONT_DIR / "ar-regular.ttf", FONT_DIR / "ar-bold.ttf"),
}

PRODUCT_IMAGES = {
    "meat": ASSETS / "products" / "gogi.webp",
    "nutrition": ASSETS / "products" / "yeongyang.webp",
    "berry": ASSETS / "products" / "berry.webp",
    "baked": ASSETS / "products" / "gupbbang.webp",
    "fresh": ASSETS / "products" / "fresh.webp",
    "mungs": ASSETS / "products" / "mungs.webp",
    "dental": ASSETS / "products" / "chika.webp",
    "meatless": ASSETS / "products" / "meatless.webp",
}

FONT_SOURCES = {
    "ko": (Path("/System/Library/Fonts/AppleSDGothicNeo.ttc"), (0, 6)),
    "cjk": (Path("/System/Library/Fonts/Hiragino Sans GB.ttc"), (0, 2)),
    "th": (Path("/System/Library/Fonts/Supplemental/Thonburi.ttc"), (0, 1)),
    "ar": (Path("/System/Library/Fonts/GeezaPro.ttc"), (0, 1)),
}


def prepare_font_files() -> None:
    """Extract the required macOS TTC faces into the ignored build cache."""
    FONT_DIR.mkdir(parents=True, exist_ok=True)
    for key, (collection_path, indices) in FONT_SOURCES.items():
        regular, bold = FONT_FILES[key]
        if regular.exists() and bold.exists():
            continue
        if not collection_path.exists():
            raise FileNotFoundError(f"Required system font is unavailable: {collection_path}")
        collection = TTCollection(str(collection_path))
        collection.fonts[indices[0]].save(regular)
        collection.fonts[indices[1]].save(bold)


def ensure_inputs() -> None:
    missing = []
    for regular, bold in FONT_FILES.values():
        if not regular.exists():
            missing.append(str(regular))
        if not bold.exists():
            missing.append(str(bold))
    for path in list(PRODUCT_IMAGES.values()) + [
        ASSETS / "hero-dog-companion.webp",
        ASSETS / "hero-dog-treats.webp",
        ASSETS / "team_walk.webp",
        ASSETS / "make_oem.webp",
        ASSETS / "make_ingredient.webp",
        ASSETS / "make_supply.webp",
        ASSETS / "approach_remove.webp",
        ASSETS / "approach_balance.webp",
        ASSETS / "lockup_zerolabs.png",
        ASSETS / "lockup_companimal.png",
    ]:
        if not path.exists():
            missing.append(str(path))
    if missing:
        raise FileNotFoundError("Missing brochure inputs:\n" + "\n".join(missing))


def rgb_css(color: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{round(v * 255):02x}" for v in color)


def css_for(lang: str) -> tuple[str, fitz.Archive]:
    font_key = LANGUAGES[lang]["font"]
    regular, bold = FONT_FILES[font_key]
    archive = fitz.Archive(str(regular.parent))
    direction = LANGUAGES[lang]["dir"]
    align = "right" if direction == "rtl" else "left"
    css = f"""
    @font-face {{ font-family: Brochure; src: url('{regular.name}'); font-weight: 400; }}
    @font-face {{ font-family: Brochure; src: url('{bold.name}'); font-weight: 700; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Brochure; direction: {direction}; text-align: {align}; color: #16241a; }}
    p, h1, h2, h3, h4 {{ margin: 0; padding: 0; }}
    .kicker {{ color: #a57d30; font-size: 10pt; font-weight: 700; letter-spacing: 1.4pt; }}
    .title {{ font-size: 28pt; line-height: 1.18; font-weight: 700; }}
    .subtitle {{ font-size: 12pt; line-height: 1.55; color: #506056; }}
    .white {{ color: #ffffff; }}
    .soft {{ color: #dce2dc; }}
    .gold {{ color: #d8b36a; }}
    .body {{ font-size: 11.5pt; line-height: 1.65; }}
    .small {{ font-size: 8.5pt; line-height: 1.5; }}
    .label {{ font-size: 9pt; font-weight: 700; color: #a57d30; }}
    .value {{ font-size: 12pt; line-height: 1.45; font-weight: 700; }}
    .card-title {{ font-size: 16pt; font-weight: 700; line-height: 1.25; }}
    .card-body {{ font-size: 9.5pt; color: #506056; line-height: 1.55; }}
    .metric {{ font-size: 25pt; font-weight: 700; color: #d8b36a; }}
    .metric-label {{ font-size: 8.5pt; line-height: 1.35; color: #e6ece6; }}
    ul {{ margin: 5pt 0 0 0; padding-inline-start: 15pt; }}
    li {{ font-size: 9.5pt; line-height: 1.5; margin-bottom: 2pt; }}
    """
    return css, archive


def add_html(page: fitz.Page, rect: fitz.Rect, markup: str, lang: str, *, scale_low: float = 0.68) -> None:
    css, archive = css_for(lang)
    spare, scale = page.insert_htmlbox(rect, markup, css=css, archive=archive, scale_low=scale_low)
    if spare < -0.01:
        raise RuntimeError(f"Text overflow on page {page.number + 1}: spare={spare}, scale={scale}")


def add_image_cover(page: fitz.Page, rect: fitz.Rect, path: Path, opacity: float | None = None) -> None:
    path = compatible_image(path)
    page.insert_image(rect, filename=str(path), keep_proportion=False)
    if opacity is not None:
        page.draw_rect(rect, color=None, fill=FOREST, fill_opacity=opacity, overlay=True)


def add_image_fit(page: fitz.Page, rect: fitz.Rect, path: Path, *, radius: float = 0) -> None:
    # PyMuPDF clipping is rectangular; the surrounding card provides the visual radius.
    path = compatible_image(path)
    page.insert_image(rect, filename=str(path), keep_proportion=True)
    if radius:
        page.draw_rect(rect, color=(0.84, 0.82, 0.76), width=0.5, radius=radius, overlay=True)


def add_logo(page: fitz.Page, kind: str, rect: fitz.Rect) -> None:
    path = ASSETS / ("lockup_zerolabs.png" if kind == "zero" else "lockup_companimal.png")
    page.insert_image(rect, filename=str(path), keep_proportion=True, overlay=True)


def compatible_image(path: Path) -> Path:
    """Return a PNG copy for formats unsupported by the local MuPDF build."""
    if path.suffix.lower() != ".webp":
        return path
    cache_dir = TMP / "image-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / f"{path.parent.name}-{path.stem}.png"
    if not target.exists() or target.stat().st_mtime < path.stat().st_mtime:
        Image.open(path).convert("RGB").save(target, optimize=True)
    return target


def new_page(doc: fitz.Document, fill: tuple[float, float, float] = CREAM) -> fitz.Page:
    page = doc.new_page(width=PAGE.width, height=PAGE.height)
    page.draw_rect(PAGE, color=None, fill=fill)
    return page


def add_footer(page: fitz.Page, page_no: int, total: int, lang: str, *, light: bool = False) -> None:
    color = "#dce2dc" if light else "#657268"
    direction = LANGUAGES[lang]["dir"]
    left = "ZERO LABS · Companimal Co., Ltd."
    markup = f'<p class="small" style="color:{color}; direction:{direction}">{html.escape(left)}</p>'
    add_html(page, fitz.Rect(42, 810, 440, 830), markup, lang)
    add_html(page, fitz.Rect(500, 810, 553, 830), f'<p class="small" style="color:{color}; text-align:right">{page_no:02d} / {total:02d}</p>', lang)


def title_block(page: fitz.Page, lang: str, kicker: str, title: str, subtitle: str = "", *, y: float = 48, light: bool = False) -> None:
    classes = "title white" if light else "title"
    subtitle_class = "subtitle soft" if light else "subtitle"
    markup = f'<p class="kicker">{html.escape(kicker)}</p><p class="{classes}" style="margin-top:9pt">{html.escape(title)}</p>'
    if subtitle:
        markup += f'<p class="{subtitle_class}" style="margin-top:11pt">{html.escape(subtitle)}</p>'
    add_html(page, fitz.Rect(42, y, 553, y + 125), markup, lang)


def qr_png(url: str, name: str) -> Path:
    TMP.mkdir(parents=True, exist_ok=True)
    target = TMP / name
    img = qrcode.make(url)
    img.save(target)
    return target


def company_brochure(lang: str) -> fitz.Document:
    c = COMPANY_CONTENT[lang]
    doc = fitz.open()
    total = 8

    # 1. Cover
    p = new_page(doc, FOREST)
    add_image_cover(p, PAGE, ASSETS / "hero-dog-companion.webp", 0.53)
    p.draw_rect(fitz.Rect(0, 0, 16, 842), color=None, fill=GOLD)
    add_logo(p, "company", fitz.Rect(42, 46, 138, 138))
    add_html(p, fitz.Rect(42, 180, 540, 440), f'<p class="kicker gold">{html.escape(c["cover_badge"])}</p><p class="title white" style="font-size:35pt; margin-top:14pt">{html.escape(c["cover_title"]).replace(chr(10), "<br>")}</p><p class="subtitle soft" style="margin-top:18pt">{html.escape(c["cover_subtitle"])}</p>', lang)
    add_html(p, fitz.Rect(42, 740, 550, 790), '<p class="small white">COMPANION ANIMAL BUSINESS · INCHEON, KOREA</p>', lang)

    # 2. Overview
    p = new_page(doc)
    title_block(p, lang, c["overview_kicker"], c["overview_title"], c["overview_body"])
    p.draw_rect(fitz.Rect(42, 210, 553, 355), radius=0.08, color=None, fill=FOREST)
    metric_w = 119
    for i, (value, label) in enumerate(c["metrics"]):
        x = 54 + i * 124
        add_html(p, fitz.Rect(x, 235, x + metric_w, 328), f'<p class="metric">{html.escape(value)}</p><p class="metric-label" style="margin-top:5pt">{html.escape(label)}</p>', lang)
        if i < 3:
            p.draw_line(fitz.Point(x + metric_w, 238), fitz.Point(x + metric_w, 326), color=MID_GREEN, width=1)
    add_image_cover(p, fitz.Rect(42, 390, 280, 755), ASSETS / "team_walk.webp")
    p.draw_rect(fitz.Rect(302, 390, 553, 755), radius=0.05, color=None, fill=CREAM_2)
    fact_markup = "".join(f'<p class="value" style="margin-bottom:19pt">{html.escape(item)}</p>' for item in c["facts"])
    add_html(p, fitz.Rect(328, 426, 528, 726), fact_markup, lang)
    add_footer(p, 2, total, lang)

    # 3. Principles
    p = new_page(doc)
    title_block(p, lang, c["principles_kicker"], c["principles_title"])
    principle_images = [ASSETS / "approach_remove.webp", ASSETS / "approach_balance.webp", ASSETS / "hero-dog-treats.webp"]
    for i, ((label, body), image_path) in enumerate(zip(c["principles"], principle_images)):
        y = 155 + i * 204
        p.draw_rect(fitz.Rect(42, y, 553, y + 176), radius=0.08, color=None, fill=WHITE)
        add_image_cover(p, fitz.Rect(42, y, 245, y + 176), image_path)
        add_html(p, fitz.Rect(270, y + 31, 526, y + 147), f'<p class="kicker">0{i + 1} · {html.escape(label)}</p><p class="card-body" style="font-size:11pt; margin-top:11pt">{html.escape(body)}</p>', lang)
    add_footer(p, 3, total, lang)

    # 4. Production
    p = new_page(doc, FOREST)
    title_block(p, lang, c["production_kicker"], c["production_title"], light=True)
    production_images = [ASSETS / "make_oem.webp", ASSETS / "make_ingredient.webp", ASSETS / "make_supply.webp"]
    if lang in {"th", "ar"}:
        for i, ((label, body), image_path) in enumerate(zip(c["production"], production_images)):
            y = 170 + i * 184
            p.draw_rect(fitz.Rect(42, y, 553, y + 160), radius=0.06, color=None, fill=GREEN)
            add_image_cover(p, fitz.Rect(42, y, 226, y + 160), image_path)
            add_html(p, fitz.Rect(252, y + 28, 526, y + 138), f'<p class="card-title white">{html.escape(label)}</p><p class="card-body soft" style="font-size:9pt; margin-top:9pt">{html.escape(body)}</p>', lang, scale_low=0.65)
    else:
        for i, ((label, body), image_path) in enumerate(zip(c["production"], production_images)):
            x = 42 + i * 171
            add_image_cover(p, fitz.Rect(x, 185, x + 154, 390), image_path)
            p.draw_rect(fitz.Rect(x, 410, x + 154, 700), radius=0.06, color=None, fill=GREEN)
            add_html(
                p,
                fitz.Rect(x + 15, 440, x + 139, 676),
                f'<p class="card-title white" style="font-size:13pt">{html.escape(label)}</p><p class="card-body soft" style="font-size:8.5pt; margin-top:10pt">{html.escape(body)}</p>',
                lang,
                scale_low=0.50,
            )
    add_footer(p, 4, total, lang, light=True)

    # 5. Portfolio
    p = new_page(doc)
    title_block(p, lang, c["portfolio_kicker"], c["portfolio_title"], c["portfolio_subtitle"])
    for i, ((name, pack), image_path) in enumerate(zip(c["products"], PRODUCT_IMAGES.values())):
        row, col = divmod(i, 4)
        x = 42 + col * 129
        y = 182 + row * 268
        p.draw_rect(fitz.Rect(x, y, x + 113, y + 242), radius=0.06, color=None, fill=WHITE)
        add_image_fit(p, fitz.Rect(x + 5, y + 5, x + 108, y + 108), image_path)
        add_html(p, fitz.Rect(x + 12, y + 130, x + 101, y + 222), f'<p class="card-title" style="font-size:12pt">{html.escape(name)}</p><p class="label" style="margin-top:9pt">{html.escape(pack)}</p>', lang)
    add_footer(p, 5, total, lang)

    # 6. Milestones
    p = new_page(doc, FOREST)
    title_block(p, lang, c["history_kicker"], c["history_title"], c["history_subtitle"], light=True)
    p.draw_line(fitz.Point(92, 210), fitz.Point(92, 690), color=GOLD, width=2)
    for i, (year, body) in enumerate(c["history"]):
        y = 208 + i * 125
        p.draw_circle(fitz.Point(92, y + 16), 6, color=GOLD, fill=GOLD)
        add_html(p, fitz.Rect(122, y, 530, y + 98), f'<p class="metric" style="font-size:19pt">{html.escape(year)}</p><p class="body soft" style="margin-top:5pt">{html.escape(body)}</p>', lang)
    add_footer(p, 6, total, lang, light=True)

    # 7. Partnership
    p = new_page(doc)
    title_block(p, lang, c["partner_kicker"], c["partner_title"], c["partner_body"])
    add_image_cover(p, fitz.Rect(42, 205, 553, 475), ASSETS / "team_walk.webp")
    for i, (label, body) in enumerate(c["partner_points"]):
        x = 42 + i * 171
        p.draw_rect(fitz.Rect(x, 500, x + 154, 705), radius=0.06, color=None, fill=WHITE)
        add_html(p, fitz.Rect(x + 16, 528, x + 138, 676), f'<p class="kicker">0{i + 1}</p><p class="card-title" style="margin-top:9pt">{html.escape(label)}</p><p class="card-body" style="margin-top:11pt">{html.escape(body)}</p>', lang)
    add_footer(p, 7, total, lang)

    # 8. Contact
    p = new_page(doc, FOREST)
    add_logo(p, "company", fitz.Rect(42, 44, 126, 126))
    title_block(p, lang, c["contact_kicker"], c["contact_title"], c["contact_subtitle"], y=152, light=True)
    labels = c["contact_labels"]
    for i, (label, value) in enumerate(zip(labels, CONTACT_VALUES)):
        row, col = divmod(i, 2)
        x = 42 + col * 261
        y = 315 + row * 98
        add_html(p, fitz.Rect(x, y, x + 240, y + 84), f'<p class="label">{html.escape(label)}</p><p class="value white" style="font-size:9.5pt; margin-top:5pt">{html.escape(value)}</p>', lang)
        if value.startswith("http"):
            p.insert_link({"kind": fitz.LINK_URI, "from": fitz.Rect(x, y, x + 240, y + 84), "uri": value})
        elif "@" in value:
            p.insert_link({"kind": fitz.LINK_URI, "from": fitz.Rect(x, y, x + 240, y + 84), "uri": f"mailto:{value}"})
    q1 = qr_png("https://companimal.kr", "qr-company.png")
    q2 = qr_png("https://pf.kakao.com/_xnyDcs", "qr-kakao.png")
    p.draw_rect(fitz.Rect(42, 638, 137, 733), radius=0.05, color=None, fill=WHITE)
    p.draw_rect(fitz.Rect(154, 638, 249, 733), radius=0.05, color=None, fill=WHITE)
    add_image_fit(p, fitz.Rect(48, 644, 131, 727), q1)
    add_image_fit(p, fitz.Rect(160, 644, 243, 727), q2)
    add_html(p, fitz.Rect(278, 650, 553, 730), f'<p class="small soft">{html.escape(c["disclosure"])}</p>', lang)
    add_footer(p, 8, total, lang, light=True)

    doc.set_metadata({"title": c["title"], "author": "Companimal Co., Ltd.", "subject": "Company profile", "keywords": f"Companimal, ZERO LABS, {LANGUAGES[lang]['locale']}"})
    doc.subset_fonts()
    return doc


def product_card(page: fitz.Page, lang: str, item: tuple[str, str, list[str], str], image_path: Path, rect: fitz.Rect, *, accent: tuple[float, float, float]) -> None:
    name, description, bullets, pack = item
    page.draw_rect(rect, radius=0.05, color=None, fill=WHITE)
    image_rect = fitz.Rect(rect.x0 + 10, rect.y0 + 10, rect.x0 + 185, rect.y1 - 10)
    add_image_fit(page, image_rect, image_path)
    text_rect = fitz.Rect(rect.x0 + 210, rect.y0 + 24, rect.x1 - 22, rect.y1 - 18)
    bullet_html = "".join(f"<li>{html.escape(b)}</li>" for b in bullets)
    add_html(page, text_rect, f'<p class="label">{html.escape(pack)}</p><p class="card-title" style="font-size:21pt; margin-top:7pt">{html.escape(name)}</p><p class="card-body" style="font-size:10.5pt; margin-top:10pt">{html.escape(description)}</p><ul>{bullet_html}</ul>', lang)
    page.draw_rect(fitz.Rect(rect.x0, rect.y0, rect.x0 + 5, rect.y1), color=None, fill=accent)


def product_brochure(lang: str) -> fitz.Document:
    c = PRODUCT_CONTENT[lang]
    doc = fitz.open()
    total = 10

    # 1. Cover
    p = new_page(doc, FOREST)
    add_image_cover(p, PAGE, ASSETS / "hero-dog-treats.webp", 0.50)
    add_logo(p, "zero", fitz.Rect(42, 48, 155, 132))
    add_html(p, fitz.Rect(42, 200, 548, 480), f'<p class="kicker gold">{html.escape(c["cover_version"])}</p><p class="title white" style="font-size:38pt; margin-top:13pt">{html.escape(c["title"])}</p><p class="subtitle soft" style="font-size:14pt; margin-top:18pt">{html.escape(c["cover_tagline"])}</p>', lang)
    p.draw_rect(fitz.Rect(42, 735, 553, 737), color=None, fill=GOLD)
    add_html(p, fitz.Rect(42, 754, 553, 790), '<p class="small white">DOG TREAT COLLECTION · MADE IN KOREA</p>', lang)

    # 2. Welcome and index
    p = new_page(doc)
    title_block(p, lang, "ZERO LABS", c["greeting_title"])
    greeting_markup = "".join(f'<p class="body" style="margin-bottom:12pt">{html.escape(paragraph)}</p>' for paragraph in c["greeting"])
    add_html(p, fitz.Rect(42, 150, 553, 330), greeting_markup, lang)
    p.draw_rect(fitz.Rect(42, 360, 553, 744), radius=0.04, color=None, fill=FOREST)
    add_html(p, fitz.Rect(68, 389, 526, 434), f'<p class="card-title white">{html.escape(c["catalog_title"])}</p>', lang)
    for i, item in enumerate(c["catalog"]):
        row, col = divmod(i, 3)
        x = 68 + col * 154
        y = 465 + row * 72
        add_html(p, fitz.Rect(x, y, x + 138, y + 50), f'<p class="label">0{i + 1}</p><p class="value white" style="font-size:9.5pt; margin-top:3pt">{html.escape(item)}</p>', lang)
    add_footer(p, 2, total, lang)

    page_specs = [
        ("MEAT JERKY", [("meat_1kg", PRODUCT_IMAGES["meat"]), ("meat_350g", PRODUCT_IMAGES["meat"])], GOLD),
        ("NUTRITION JERKY", [("nutrition_1kg", PRODUCT_IMAGES["nutrition"]), ("nutrition_350g", PRODUCT_IMAGES["nutrition"])], (0.44, 0.61, 0.38)),
        ("BERRY JERKY", [("berry_1kg", PRODUCT_IMAGES["berry"]), ("berry_400g", PRODUCT_IMAGES["berry"])], (0.64, 0.31, 0.43)),
        ("BAKED TREATS", [("baked_1kg", PRODUCT_IMAGES["baked"]), ("baked_200g", PRODUCT_IMAGES["baked"])], (0.72, 0.45, 0.22)),
        ("CEREAL TREATS", [("fresh_ring", PRODUCT_IMAGES["fresh"]), ("mungs", PRODUCT_IMAGES["mungs"])], (0.32, 0.55, 0.51)),
        ("DAILY VARIETY", [("dental", PRODUCT_IMAGES["dental"]), ("meatless", PRODUCT_IMAGES["meatless"])], (0.50, 0.38, 0.60)),
    ]
    for page_no, (kicker, items, accent) in enumerate(page_specs, start=3):
        p = new_page(doc)
        first_name = c["products"][items[0][0]][0]
        second_name = c["products"][items[1][0]][0]
        page_title = first_name if first_name == second_name else f"{first_name} · {second_name}"
        title_block(p, lang, kicker, page_title)
        product_card(p, lang, c["products"][items[0][0]], items[0][1], fitz.Rect(42, 160, 553, 418), accent=accent)
        product_card(p, lang, c["products"][items[1][0]], items[1][1], fitz.Rect(42, 445, 553, 703), accent=accent)
        add_footer(p, page_no, total, lang)

    # 9. Trial packs
    p = new_page(doc, FOREST)
    title_block(p, lang, "TRY THE RANGE", c["trial_title"], c["trial_intro"], light=True)
    for i, (key, image_path) in enumerate(PRODUCT_IMAGES.items()):
        row, col = divmod(i, 4)
        x = 42 + col * 129
        y = 210 + row * 225
        p.draw_rect(fitz.Rect(x, y, x + 113, y + 198), radius=0.06, color=None, fill=WHITE)
        add_image_fit(p, fitz.Rect(x + 6, y + 6, x + 107, y + 107), image_path)
        product_key = {"meat": "meat_350g", "nutrition": "nutrition_350g", "berry": "berry_400g", "baked": "baked_200g", "fresh": "fresh_ring", "mungs": "mungs", "dental": "dental", "meatless": "meatless"}[key]
        product_name = c["products"][product_key][0]
        add_html(p, fitz.Rect(x + 10, y + 126, x + 103, y + 183), f'<p class="value" style="font-size:9.5pt">{html.escape(product_name)}</p><p class="label" style="margin-top:5pt">30 g</p>', lang)
    add_footer(p, 9, total, lang, light=True)

    # 10. Contact
    p = new_page(doc, FOREST)
    add_logo(p, "zero", fitz.Rect(42, 48, 155, 132))
    title_block(p, lang, "CONTACT", c["contact_title"], c["contact_intro"], y=175, light=True)
    for i, (label, value) in enumerate(zip(c["contact_labels"], PRODUCT_CONTACT_VALUES)):
        y = 325 + i * 85
        add_html(p, fitz.Rect(42, y, 420, y + 70), f'<p class="label">{html.escape(label)}</p><p class="value white" style="font-size:10.5pt; margin-top:5pt">{html.escape(value)}</p>', lang)
        uri = f"mailto:{value}" if "@" in value else value if value.startswith("http") else None
        if uri:
            p.insert_link({"kind": fitz.LINK_URI, "from": fitz.Rect(42, y, 420, y + 70), "uri": uri})
    q1 = qr_png("https://companimal.kr", "qr-company.png")
    q2 = qr_png("https://pf.kakao.com/_xnyDcs", "qr-kakao.png")
    p.draw_rect(fitz.Rect(425, 325, 553, 453), radius=0.06, color=None, fill=WHITE)
    p.draw_rect(fitz.Rect(425, 480, 553, 608), radius=0.06, color=None, fill=WHITE)
    add_image_fit(p, fitz.Rect(433, 333, 545, 445), q1)
    add_image_fit(p, fitz.Rect(433, 488, 545, 600), q2)
    add_html(p, fitz.Rect(42, 718, 553, 772), f'<p class="small soft">{html.escape(c["contact_disclosure"])}</p>', lang)
    add_footer(p, 10, total, lang, light=True)

    doc.set_metadata({"title": c["title"], "author": "Companimal Co., Ltd.", "subject": "ZERO LABS product brochure", "keywords": f"ZERO LABS, dog treats, {LANGUAGES[lang]['locale']}"})
    doc.subset_fonts()
    return doc


def save_with_language(doc: fitz.Document, path: Path, locale: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = path.with_suffix(".raw.pdf")
    doc.save(raw, garbage=4, deflate=True, clean=True)
    doc.close()
    reader = PdfReader(str(raw))
    writer = PdfWriter()
    writer.append_pages_from_reader(reader)
    if reader.metadata:
        writer.add_metadata({k: str(v) for k, v in reader.metadata.items() if v is not None})
    writer._root_object.update({NameObject("/Lang"): TextStringObject(locale)})
    with path.open("wb") as handle:
        writer.write(handle)
    raw.unlink()


def render_pdf(path: Path) -> list[Path]:
    target = RENDER_DIR / path.stem
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    doc = fitz.open(path)
    results = []
    matrix = fitz.Matrix(1.45, 1.45)
    for index, page in enumerate(doc):
        out = target / f"page-{index + 1:02d}.png"
        page.get_pixmap(matrix=matrix, alpha=False).save(out)
        results.append(out)
    doc.close()
    return results


def contact_sheet(images: list[Path], output: Path, columns: int = 4) -> None:
    thumbs = []
    for path in images:
        image = Image.open(path).convert("RGB")
        image.thumbnail((220, 310))
        thumbs.append(image.copy())
    rows = (len(thumbs) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * 230, rows * 320), "white")
    for i, image in enumerate(thumbs):
        x = (i % columns) * 230 + 5
        y = (i // columns) * 320 + 5
        sheet.paste(image, (x, y))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, quality=92)


def build(languages: list[str]) -> dict[str, dict[str, object]]:
    prepare_font_files()
    ensure_inputs()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    results: dict[str, dict[str, object]] = {}
    for lang in languages:
        company_path = OUTPUT / f"company-profile-{lang}.pdf"
        product_path = OUTPUT / f"product-brochure-{lang}.pdf"
        save_with_language(company_brochure(lang), company_path, LANGUAGES[lang]["locale"])
        save_with_language(product_brochure(lang), product_path, LANGUAGES[lang]["locale"])
        company_renders = render_pdf(company_path)
        product_renders = render_pdf(product_path)
        company_sheet = RENDER_DIR / f"company-profile-{lang}-contact-sheet.png"
        product_sheet = RENDER_DIR / f"product-brochure-{lang}-contact-sheet.png"
        contact_sheet(company_renders, company_sheet)
        contact_sheet(product_renders, product_sheet)
        results[lang] = {
            "label": LANGUAGES[lang]["label"],
            "locale": LANGUAGES[lang]["locale"],
            "company": {"path": str(company_path.relative_to(ROOT)), "bytes": company_path.stat().st_size, "pages": len(company_renders)},
            "product": {"path": str(product_path.relative_to(ROOT)), "bytes": product_path.stat().st_size, "pages": len(product_renders)},
        }
    if "ko" in languages:
        shutil.copy2(RENDER_DIR / "company-profile-ko-contact-sheet.png", OUTPUT / "company-profile-preview-ko.png")
    manifest = OUTPUT / "brochure-files.json"
    manifest.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--languages", nargs="+", default=list(LANGUAGES), choices=list(LANGUAGES))
    args = parser.parse_args()
    print(json.dumps(build(args.languages), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Build six Korean brochure design prototypes without changing live downloads.

Each option contains four representative pages so the choice is based on a
real editorial system, not a cover-only mood board.
"""

from __future__ import annotations

import html
import shutil
from pathlib import Path

import fitz
from PIL import Image

from brochure_content import COMPANY_CONTENT, PRODUCT_CONTENT
from build_brochures import (
    ASSETS,
    COMPANY_DETAIL,
    COMPANY_PAGE,
    CREAM,
    CREAM_2,
    FOREST,
    GOLD,
    GREEN,
    HOMEPAGE_COMPANY,
    MID_GREEN,
    PRODUCT_IMAGES,
    WHITE,
    add_html,
    add_image_cover,
    add_image_fit,
    add_logo,
    contact_sheet,
    ensure_inputs,
    new_company_page,
    prepare_font_files,
    render_pdf,
    save_with_language,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf" / "concepts"
PREVIEWS = OUTPUT / "previews"
TMP_CONCEPTS = ROOT / "tmp" / "pdfs" / "concepts"
KO = "ko"

COMPANY_OPTIONS = {
    "a": "홈페이지 에디토리얼",
    "b": "세일즈 프루프",
    "c": "브랜드 스토리북",
}
PRODUCT_OPTIONS = {
    "a": "비주얼 카탈로그",
    "b": "바이어 스펙북",
    "c": "원료·제품 스토리",
}


def page(doc: fitz.Document, fill=CREAM) -> fitz.Page:
    return new_company_page(doc, fill)


def footer(p: fitz.Page, option: str, page_no: int, total: int, *, light: bool = False) -> None:
    color = "#dce2dc" if light else "#657268"
    add_html(
        p,
        fitz.Rect(48, 558, 680, 579),
        f'<p style="font-size:7.2pt;color:{color}">ZERO LABS · {html.escape(option)} · DESIGN PROTOTYPE</p>',
        KO,
        scale_low=1,
    )
    add_html(
        p,
        fitz.Rect(742, 558, 794, 579),
        f'<p style="font-size:7.2pt;color:{color};text-align:right">{page_no:02d} / {total:02d}</p>',
        KO,
        scale_low=1,
    )


def label(p: fitz.Page, rect: fitz.Rect, text: str, *, light: bool = False) -> None:
    color = "#d8b36a" if light else "#a57d30"
    add_html(
        p,
        rect,
        f'<p style="font-size:8.2pt;font-weight:700;letter-spacing:1.4pt;color:{color}">{html.escape(text)}</p>',
        KO,
        scale_low=1,
    )


def headline(
    p: fitz.Page,
    rect: fitz.Rect,
    title: str,
    body: str = "",
    *,
    light: bool = False,
    size: float = 28,
) -> None:
    title_color = "#ffffff" if light else "#16241a"
    body_color = "#dce2dc" if light else "#506056"
    markup = f'<p style="font-size:{size}pt;line-height:1.14;font-weight:700;color:{title_color}">{html.escape(title)}</p>'
    if body:
        markup += f'<p style="font-size:9.2pt;line-height:1.5;color:{body_color};margin-top:10pt">{html.escape(body)}</p>'
    add_html(p, rect, markup, KO, scale_low=0.82)


def set_meta(doc: fitz.Document, title: str, subject: str) -> fitz.Document:
    doc.set_metadata({
        "title": title,
        "author": "Companimal Co., Ltd.",
        "subject": subject,
        "keywords": "ZERO LABS, Companimal, brochure design prototype",
    })
    return doc


def company_option_a() -> fitz.Document:
    """Homepage editorial: the user's preferred warm homepage visual grammar."""
    doc = fitz.open()
    c = COMPANY_CONTENT[KO]
    home = HOMEPAGE_COMPANY[KO]
    total = 4
    option = "회사소개서 A · 홈페이지 에디토리얼"

    p = page(doc, FOREST)
    add_image_cover(p, fitz.Rect(410, 0, 842, 595), ASSETS / "hero-dog-companion.webp")
    p.draw_rect(fitz.Rect(370, 0, 510, 595), color=None, fill=FOREST, fill_opacity=0.62, overlay=True)
    p.draw_rect(fitz.Rect(0, 0, 12, 595), color=None, fill=GOLD)
    add_logo(p, "company", fitz.Rect(50, 42, 116, 108))
    add_logo(p, "zero", fitz.Rect(138, 48, 258, 101))
    label(p, fitz.Rect(50, 150, 355, 174), "COMPANY PROFILE · 2026", light=True)
    headline(p, fitz.Rect(50, 190, 380, 355), "반려견이 매일 먹는 간식의\n기준을 다시 세웁니다.", "홈페이지의 대표 인사말·팀·브랜드·유통 정보를 한 흐름으로 연결한 회사소개서", light=True, size=34)
    add_html(p, fitz.Rect(50, 458, 365, 510), '<p style="font-size:8.5pt;color:#d8b36a;font-weight:700">OPTION A · PHOTO-LED EDITORIAL</p>', KO)
    footer(p, option, 1, total, light=True)

    p = page(doc)
    ceo = home["ceo"]
    team = home["team"]
    label(p, fitz.Rect(48, 38, 300, 60), "PEOPLE & CULTURE")
    headline(p, fitz.Rect(48, 68, 746, 126), "사람이 만드는 브랜드", "대표의 기준과 팀의 일하는 방식을 한 페이지에서 보여 줍니다.", size=25)
    add_image_cover(p, fitz.Rect(48, 156, 300, 510), ASSETS / "ceo_jangseonghwan.webp")
    add_html(p, fitz.Rect(324, 164, 776, 265), f'<p style="font-size:16pt;line-height:1.5;font-weight:700">“{html.escape(ceo[2])}”</p><p style="font-size:9pt;color:#506056;margin-top:14pt">{html.escape(ceo[3])} · {html.escape(ceo[4])}</p>', KO, scale_low=0.86)
    p.draw_line(fitz.Point(324, 288), fitz.Point(776, 288), color=GOLD, width=1.2)
    add_html(p, fitz.Rect(324, 315, 776, 385), f'<p style="font-size:17pt;font-weight:700">{html.escape(team[1])}</p><p style="font-size:9pt;line-height:1.5;color:#506056;margin-top:9pt">{html.escape(team[2])}</p>', KO, scale_low=0.86)
    for index, asset in enumerate(("tee_black.webp", "tee_white.webp")):
        x = 324 + index * 226
        p.draw_rect(fitz.Rect(x, 407, x + 210, 510), radius=0.025, color=(0.86, 0.82, 0.74), fill=WHITE, width=0.5)
        add_image_fit(p, fitz.Rect(x + 8, 414, x + 202, 497), ASSETS / asset)
    footer(p, option, 2, total)

    p = page(doc, FOREST)
    label(p, fitz.Rect(48, 35, 300, 58), "BRAND MILESTONES", light=True)
    headline(p, fitz.Rect(48, 65, 746, 120), "브랜드가 걸어온 길 · 2021–2022", "고정 높이 카드 없이, 글이 차지하는 만큼만 쓰는 2열 편집형 연혁", light=True, size=25)
    for column, (year, items) in enumerate(c["history"][:2]):
        x = 48 + column * 390
        add_html(p, fitz.Rect(x, 155, x + 340, 205), f'<p style="font-size:29pt;font-weight:700;color:#d8b36a">{year}</p>', KO)
        p.draw_line(fitz.Point(x, 214), fitz.Point(x + 340, 214), color=GOLD, width=1.1)
        rows = "".join(
            f'<li style="font-size:8.9pt;line-height:1.42;margin-bottom:4pt;{("font-weight:700;color:#ffffff" if i == 0 else "color:#dce2dc")}">{html.escape(item)}</li>'
            for i, item in enumerate(items)
        )
        add_html(p, fitz.Rect(x, 235, x + 340, 475), f'<ul style="padding-inline-start:15pt;margin:0">{rows}</ul>', KO, scale_low=0.9)
    p.draw_rect(fitz.Rect(48, 458, 794, 528), radius=0.02, color=None, fill=GREEN)
    highlights = [("14개", "전국 대리점 계약"), ("2년", "K-PET 연속 참가"), ("온·오프라인", "유통 채널 확장")]
    for i, (value, description) in enumerate(highlights):
        x = 72 + i * 244
        add_html(p, fitz.Rect(x, 475, x + 210, 516), f'<p style="font-size:14pt;color:#d8b36a;font-weight:700">{value}</p><p style="font-size:7.5pt;color:#dce2dc;margin-top:4pt">{description}</p>', KO)
    footer(p, option, 3, total, light=True)

    p = page(doc)
    profile = home["profile"][3]
    label(p, fitz.Rect(48, 35, 300, 58), "COMPANY PROFILE")
    headline(p, fitz.Rect(48, 65, 746, 118), "거래 전에 필요한 회사 정보", "라벨과 값을 한 줄에서 분명히 구분하고, 문의 행동까지 바로 연결합니다.", size=25)
    for i, (name, value, detail) in enumerate(profile):
        row, col = divmod(i, 2)
        x = 48 + col * 380
        y = 155 + row * 101
        p.draw_line(fitz.Point(x, y), fitz.Point(x + 348, y), color=(0.79, 0.77, 0.70), width=0.7)
        add_html(p, fitz.Rect(x, y + 16, x + 115, y + 74), f'<p style="font-size:8pt;color:#a57d30;font-weight:700">{html.escape(name)}</p>', KO)
        add_html(p, fitz.Rect(x + 120, y + 12, x + 348, y + 78), f'<p style="font-size:12pt;font-weight:700">{html.escape(value)}</p><p style="font-size:7.5pt;color:#657268;margin-top:5pt">{html.escape(detail)}</p>', KO, scale_low=0.82)
    p.draw_rect(fitz.Rect(48, 473, 794, 535), radius=0.025, color=None, fill=FOREST)
    add_html(p, fitz.Rect(70, 488, 600, 522), '<p style="font-size:11pt;color:#ffffff;font-weight:700">제품 문의 · B2B 거래 · 채널 입점 상담</p>', KO)
    add_html(p, fitz.Rect(620, 488, 772, 522), '<p style="font-size:9pt;color:#d8b36a;text-align:right;font-weight:700">companimal.kr  →</p>', KO)
    p.insert_link({"kind": fitz.LINK_URI, "from": fitz.Rect(48, 473, 794, 535), "uri": "https://companimal.kr"})
    footer(p, option, 4, total)
    return set_meta(doc, option, "Company brochure concept A")


def company_option_b() -> fitz.Document:
    """Sales proof: compact evidence and channel-oriented B2B presentation."""
    doc = fitz.open()
    c = COMPANY_CONTENT[KO]
    detail = COMPANY_DETAIL[KO]
    total = 4
    option = "회사소개서 B · 세일즈 프루프"

    p = page(doc, FOREST)
    add_image_cover(p, fitz.Rect(520, 0, 842, 595), ASSETS / "make_oem.webp")
    p.draw_rect(fitz.Rect(475, 0, 585, 595), color=None, fill=FOREST, fill_opacity=0.78, overlay=True)
    add_logo(p, "zero", fitz.Rect(48, 38, 175, 95))
    label(p, fitz.Rect(48, 145, 410, 168), "B2B COMPANY PROFILE · OPTION B", light=True)
    headline(p, fitz.Rect(48, 180, 445, 310), "제품력과 유통 실행력을\n숫자와 근거로 보여 줍니다.", "바이어가 5분 안에 회사·제품·채널·협력 포인트를 검토하도록 설계한 세일즈덱", light=True, size=31)
    metrics = [("8", "주력 제품 라인"), ("4", "판매 채널"), ("2021–26", "브랜드 연혁"), ("6,476만+", "누적 기부금(원)")]
    for i, (value, text) in enumerate(metrics):
        x = 48 + i * 112
        add_html(p, fitz.Rect(x, 410, x + 100, 485), f'<p style="font-size:20pt;color:#d8b36a;font-weight:700">{value}</p><p style="font-size:7.4pt;color:#dce2dc;margin-top:5pt">{text}</p>', KO)
    footer(p, option, 1, total, light=True)

    p = page(doc)
    label(p, fitz.Rect(48, 35, 300, 58), "CORE CAPABILITIES")
    headline(p, fitz.Rect(48, 65, 746, 118), "기획에서 공급까지 끊기지 않는 구조", "세 개의 큰 카드 대신 이미지와 근거를 결합한 짧은 증명 단위", size=25)
    assets = ("make_oem.webp", "make_ingredient.webp", "make_supply.webp")
    for i, ((title, body), asset) in enumerate(zip(c["production"], assets)):
        x = 48 + i * 249
        add_image_cover(p, fitz.Rect(x, 150, x + 229, 322), ASSETS / asset)
        p.draw_rect(fitz.Rect(x, 322, x + 229, 488), color=None, fill=FOREST)
        add_html(p, fitz.Rect(x + 16, 342, x + 213, 470), f'<p style="font-size:8pt;color:#d8b36a;font-weight:700">0{i + 1}</p><p style="font-size:14pt;color:#ffffff;font-weight:700;margin-top:7pt">{html.escape(title)}</p><p style="font-size:8.2pt;line-height:1.45;color:#dce2dc;margin-top:10pt">{html.escape(body)}</p>', KO, scale_low=0.84)
    footer(p, option, 2, total)

    p = page(doc, FOREST)
    label(p, fitz.Rect(48, 35, 300, 58), "ROUTES TO MARKET", light=True)
    headline(p, fitz.Rect(48, 65, 746, 118), "판매 채널을 목적별로 구분합니다", detail["channels"][2], light=True, size=25)
    for i, (title, body) in enumerate(detail["channel_items"]):
        y = 155 + i * 87
        p.draw_line(fitz.Point(48, y), fitz.Point(794, y), color=MID_GREEN, width=0.8)
        add_html(p, fitz.Rect(48, y + 18, 90, y + 50), f'<p style="font-size:9pt;color:#d8b36a;font-weight:700">0{i + 1}</p>', KO)
        add_html(p, fitz.Rect(110, y + 12, 355, y + 55), f'<p style="font-size:13pt;color:#ffffff;font-weight:700">{html.escape(title)}</p>', KO)
        add_html(p, fitz.Rect(390, y + 12, 794, y + 55), f'<p style="font-size:8.8pt;color:#dce2dc;line-height:1.45">{html.escape(body)}</p>', KO)
    footer(p, option, 3, total, light=True)

    p = page(doc)
    label(p, fitz.Rect(48, 35, 300, 58), "PARTNERSHIP")
    headline(p, fitz.Rect(48, 65, 746, 126), c["partner_title"], c["partner_body"], size=25)
    for i, (title, body) in enumerate(c["partner_points"]):
        y = 165 + i * 98
        p.draw_line(fitz.Point(48, y), fitz.Point(794, y), color=(0.79, 0.77, 0.70), width=0.7)
        add_html(p, fitz.Rect(48, y + 18, 92, y + 58), f'<p style="font-size:9pt;color:#a57d30;font-weight:700">0{i + 1}</p>', KO)
        add_html(p, fitz.Rect(112, y + 13, 275, y + 63), f'<p style="font-size:14pt;font-weight:700">{html.escape(title)}</p>', KO)
        add_html(p, fitz.Rect(295, y + 12, 770, y + 69), f'<p style="font-size:9pt;line-height:1.5;color:#506056">{html.escape(body)}</p>', KO)
    p.draw_rect(fitz.Rect(48, 478, 794, 535), radius=0.025, color=None, fill=GOLD)
    add_html(p, fitz.Rect(70, 492, 775, 522), '<p style="font-size:10pt;font-weight:700;color:#16241a">MOQ · 공급가 · 마진 · 리드타임은 거래 형태에 맞춰 상담합니다.  bldh2025@naver.com</p>', KO)
    footer(p, option, 4, total)
    return set_meta(doc, option, "Company brochure concept B")


def company_option_c() -> fitz.Document:
    """Brand storybook: emotional, image-led pages with selective proof."""
    doc = fitz.open()
    c = COMPANY_CONTENT[KO]
    home = HOMEPAGE_COMPANY[KO]
    total = 4
    option = "회사소개서 C · 브랜드 스토리북"

    p = page(doc)
    add_image_cover(p, fitz.Rect(0, 0, 842, 595), ASSETS / "hero-dog-treats.webp", opacity=0.33)
    p.draw_rect(fitz.Rect(0, 0, 842, 595), color=None, fill=FOREST, fill_opacity=0.40, overlay=True)
    add_logo(p, "zero", fitz.Rect(52, 42, 188, 104))
    label(p, fitz.Rect(52, 170, 450, 195), "BRAND STORY · OPTION C", light=True)
    headline(p, fitz.Rect(52, 210, 610, 390), "좋은 간식은\n함께 걷는 마음에서 시작됩니다.", "원료·제품·사람·나눔을 하나의 브랜드 이야기로 엮은 감성형 소개서", light=True, size=36)
    footer(p, option, 1, total, light=True)

    p = page(doc)
    label(p, fitz.Rect(48, 35, 300, 58), "BRAND PRINCIPLES")
    headline(p, fitz.Rect(48, 65, 746, 116), "ZERO LABS의 세 가지 원칙", "사진을 크게 쓰되 정보는 이미지 위에 억지로 올리지 않습니다.", size=25)
    assets = ("approach_remove.webp", "approach_balance.webp", "hero-dog-treats.webp")
    for i, ((title, body), asset) in enumerate(zip(c["principles"], assets)):
        x = 48 + i * 249
        add_image_cover(p, fitz.Rect(x, 145, x + 229, 354), ASSETS / asset)
        add_html(p, fitz.Rect(x, 374, x + 229, 478), f'<p style="font-size:8pt;color:#a57d30;font-weight:700">0{i + 1}</p><p style="font-size:15pt;font-weight:700;margin-top:6pt">{html.escape(title)}</p><p style="font-size:8.3pt;line-height:1.45;color:#506056;margin-top:8pt">{html.escape(body)}</p>', KO, scale_low=0.82)
    footer(p, option, 2, total)

    p = page(doc, FOREST)
    donation = home["donation"]
    add_image_cover(p, fitz.Rect(0, 0, 420, 595), ASSETS / "team_walk.webp")
    p.draw_rect(fitz.Rect(0, 390, 420, 595), color=None, fill=FOREST, fill_opacity=0.72, overlay=True)
    label(p, fitz.Rect(460, 44, 780, 67), "TEAM & RESPONSIBILITY", light=True)
    headline(p, fitz.Rect(460, 84, 790, 188), "같은 방향으로 걷는 팀", home["team"][2], light=True, size=24)
    p.draw_line(fitz.Point(460, 220), fitz.Point(790, 220), color=GOLD, width=1.2)
    add_html(p, fitz.Rect(460, 248, 790, 350), f'<p style="font-size:28pt;color:#d8b36a;font-weight:700">64,762,460원</p><p style="font-size:9pt;color:#dce2dc;margin-top:8pt">{html.escape(donation[3])}</p>', KO)
    add_html(p, fitz.Rect(460, 382, 790, 500), f'<p style="font-size:15pt;color:#ffffff;font-weight:700">{html.escape(donation[1])}</p><p style="font-size:8.5pt;line-height:1.5;color:#dce2dc;margin-top:9pt">{html.escape(donation[2])}</p>', KO)
    footer(p, option, 3, total, light=True)

    p = page(doc)
    label(p, fitz.Rect(48, 35, 300, 58), "PORTFOLIO & PARTNERS")
    headline(p, fitz.Rect(48, 65, 746, 116), "제품에서 거래까지 이어지는 한 장", "대표 제품군을 크게 보여 주고 파트너 제안은 세 문장으로 끝냅니다.", size=25)
    products = list(zip(c["products"][:4], [PRODUCT_IMAGES["meat"], PRODUCT_IMAGES["nutrition"], PRODUCT_IMAGES["berry"], PRODUCT_IMAGES["dental"]]))
    for i, ((name, pack), asset) in enumerate(products):
        x = 48 + i * 187
        p.draw_rect(fitz.Rect(x, 145, x + 169, 295), radius=0.025, color=(0.88, 0.84, 0.74), fill=WHITE, width=0.5)
        add_image_fit(p, fitz.Rect(x + 8, 153, x + 161, 272), asset)
        add_html(p, fitz.Rect(x, 305, x + 169, 350), f'<p style="font-size:9.5pt;font-weight:700">{html.escape(name)}</p><p style="font-size:7.4pt;color:#a57d30;margin-top:4pt">{html.escape(pack)}</p>', KO)
    for i, (title, body) in enumerate(c["partner_points"]):
        x = 48 + i * 249
        p.draw_line(fitz.Point(x, 390), fitz.Point(x + 220, 390), color=GOLD, width=1.0)
        add_html(p, fitz.Rect(x, 407, x + 220, 505), f'<p style="font-size:12pt;font-weight:700">{html.escape(title)}</p><p style="font-size:8pt;line-height:1.45;color:#506056;margin-top:8pt">{html.escape(body)}</p>', KO, scale_low=0.83)
    footer(p, option, 4, total)
    return set_meta(doc, option, "Company brochure concept C")


def product_option_a() -> fitz.Document:
    """Visual catalog: category and pack shots dominate every page."""
    doc = fitz.open()
    c = PRODUCT_CONTENT[KO]
    total = 4
    option = "제품소개서 A · 비주얼 카탈로그"

    p = page(doc, FOREST)
    add_image_cover(p, fitz.Rect(438, 0, 842, 595), ASSETS / "hero-dog-treats.webp")
    p.draw_rect(fitz.Rect(390, 0, 515, 595), color=None, fill=FOREST, fill_opacity=0.70, overlay=True)
    add_logo(p, "zero", fitz.Rect(50, 40, 186, 102))
    label(p, fitz.Rect(50, 155, 370, 180), "PRODUCT CATALOGUE · OPTION A", light=True)
    headline(p, fitz.Rect(50, 195, 400, 340), "제품이 먼저 보이는\nZERO LABS 카탈로그", "제품 사진을 페이지의 중심에 두고 이름·용량·핵심 설명만 짧게 배치합니다.", light=True, size=33)
    footer(p, option, 1, total, light=True)

    p = page(doc)
    label(p, fitz.Rect(48, 35, 300, 58), "PRODUCT LINEUP")
    headline(p, fitz.Rect(48, 65, 746, 112), "8개 주력 라인을 한눈에", "빈 카드 없이 이미지·제품명·포장 단위가 한 덩어리로 움직입니다.", size=25)
    image_keys = ["meat", "nutrition", "berry", "dental", "baked", "meatless", "mungs", "fresh"]
    product_names = COMPANY_CONTENT[KO]["products"]
    for i, ((name, pack), image_key) in enumerate(zip(product_names, image_keys)):
        row, col = divmod(i, 4)
        x = 48 + col * 187
        y = 140 + row * 191
        p.draw_rect(fitz.Rect(x, y, x + 169, y + 129), radius=0.025, color=(0.88, 0.84, 0.74), fill=WHITE, width=0.5)
        add_image_fit(p, fitz.Rect(x + 8, y + 7, x + 161, y + 119), PRODUCT_IMAGES[image_key])
        add_html(p, fitz.Rect(x, y + 137, x + 169, y + 180), f'<p style="font-size:9.3pt;font-weight:700">{html.escape(name)}</p><p style="font-size:7.2pt;color:#a57d30;margin-top:4pt">{html.escape(pack)}</p>', KO)
    footer(p, option, 2, total)

    p = page(doc, FOREST)
    item = c["products"]["meat_1kg"]
    add_image_fit(p, fitz.Rect(28, 34, 454, 530), PRODUCT_IMAGES["meat"])
    label(p, fitz.Rect(494, 54, 780, 78), "JERKY SERIES", light=True)
    headline(p, fitz.Rect(494, 95, 790, 185), item[0], item[1], light=True, size=29)
    for i, bullet in enumerate(item[2]):
        y = 230 + i * 62
        p.draw_line(fitz.Point(494, y), fitz.Point(790, y), color=MID_GREEN, width=0.8)
        add_html(p, fitz.Rect(494, y + 16, 530, y + 45), f'<p style="font-size:8pt;color:#d8b36a;font-weight:700">0{i + 1}</p>', KO)
        add_html(p, fitz.Rect(545, y + 12, 790, y + 50), f'<p style="font-size:10pt;color:#ffffff;font-weight:700">{html.escape(bullet)}</p>', KO)
    add_html(p, fitz.Rect(494, 435, 790, 498), f'<p style="font-size:23pt;color:#d8b36a;font-weight:700">{html.escape(item[3])}</p><p style="font-size:7.5pt;color:#dce2dc;margin-top:7pt">세부 사양은 공식 문의 채널에서 확인합니다.</p>', KO)
    footer(p, option, 3, total, light=True)

    p = page(doc)
    label(p, fitz.Rect(48, 35, 300, 58), "TRIAL & CONTACT")
    headline(p, fitz.Rect(48, 65, 746, 112), "작게 먼저, 거래는 바로", c["trial_intro"], size=25)
    trial = [("고기가득", "meat"), ("영양가득", "nutrition"), ("베리가득", "berry"), ("굽빵", "baked")]
    for i, (name, key) in enumerate(trial):
        x = 48 + i * 150
        p.draw_rect(fitz.Rect(x, 155, x + 132, 355), radius=0.025, color=(0.88, 0.84, 0.74), fill=WHITE, width=0.5)
        add_image_fit(p, fitz.Rect(x + 8, 165, x + 124, 304), PRODUCT_IMAGES[key])
        add_html(p, fitz.Rect(x, 315, x + 132, 346), f'<p style="font-size:8.5pt;font-weight:700;text-align:center">{name} · 30 g</p>', KO)
    p.draw_rect(fitz.Rect(668, 155, 794, 355), radius=0.025, color=None, fill=FOREST)
    add_html(p, fitz.Rect(686, 178, 778, 330), '<p style="font-size:8pt;color:#d8b36a;font-weight:700">B2B</p><p style="font-size:14pt;color:#ffffff;font-weight:700;margin-top:8pt">제품 문의</p><p style="font-size:7.5pt;line-height:1.5;color:#dce2dc;margin-top:14pt">공급가 · MOQ · 리드타임</p><p style="font-size:8pt;color:#d8b36a;font-weight:700;margin-top:22pt">bldh2025@naver.com</p>', KO, scale_low=0.82)
    add_html(p, fitz.Rect(48, 410, 794, 510), '<p style="font-size:16pt;font-weight:700">제품 사진은 크게, 설명은 짧게, 문의 동선은 한 번에.</p><p style="font-size:8.8pt;line-height:1.5;color:#506056;margin-top:10pt">Cambridge Treats의 카테고리 구분과 Fromm의 제품 연결 방식을 ZERO LABS의 그린 톤으로 재해석한 안입니다.</p>', KO)
    footer(p, option, 4, total)
    return set_meta(doc, option, "Product brochure concept A")


def product_option_b() -> fitz.Document:
    """Buyer specbook: compact tables and purchasing clarity."""
    doc = fitz.open()
    c = PRODUCT_CONTENT[KO]
    total = 4
    option = "제품소개서 B · 바이어 스펙북"

    p = page(doc)
    p.draw_rect(fitz.Rect(0, 0, 280, 595), color=None, fill=FOREST)
    add_logo(p, "zero", fitz.Rect(48, 42, 178, 100))
    label(p, fitz.Rect(48, 155, 245, 180), "BUYER SPECBOOK", light=True)
    headline(p, fitz.Rect(48, 195, 235, 382), "발주 검토에\n필요한 정보만\n빠르게.", "제품·포장·형태·거래 문의를 표와 규격으로 정리한 B2B 안", light=True, size=28)
    add_image_fit(p, fitz.Rect(320, 65, 794, 510), PRODUCT_IMAGES["meat"])
    footer(p, option, 1, total)

    p = page(doc)
    label(p, fitz.Rect(48, 35, 300, 58), "SKU MATRIX")
    headline(p, fitz.Rect(48, 65, 746, 112), "제품군과 포장 단위", "사진을 줄이는 대신 비교 가능한 정렬과 밀도를 우선합니다.", size=25)
    rows = [
        ("고기가득", "져키", "1 kg · 350 g", "4종", "meat"),
        ("영양가득", "져키", "1 kg · 350 g", "3종", "nutrition"),
        ("베리가득", "져키", "1 kg · 400 g", "3종", "berry"),
        ("치카하개", "발포껌", "240 g", "3종", "dental"),
        ("굽빵", "베이크드", "1 kg · 200 g", "2종", "baked"),
        ("미트리스", "식물성", "1 kg", "1종", "meatless"),
        ("멍스", "시리얼", "100 g", "1종", "mungs"),
        ("프레쉬링", "시리얼", "100 g", "1종", "fresh"),
    ]
    headers = ["제품", "유형", "포장", "구성"]
    for i, text in enumerate(headers):
        x = [160, 345, 500, 650][i]
        add_html(p, fitz.Rect(x, 140, x + 120, 168), f'<p style="font-size:7.5pt;color:#a57d30;font-weight:700">{text}</p>', KO)
    for i, (name, category, pack, count, key) in enumerate(rows):
        y = 176 + i * 43
        p.draw_line(fitz.Point(48, y), fitz.Point(794, y), color=(0.82, 0.80, 0.74), width=0.55)
        add_image_fit(p, fitz.Rect(52, y + 4, 132, y + 38), PRODUCT_IMAGES[key])
        for x, text, weight in ((160, name, 700), (345, category, 400), (500, pack, 700), (650, count, 700)):
            add_html(p, fitz.Rect(x, y + 10, x + 130, y + 36), f'<p style="font-size:8.3pt;font-weight:{weight}">{html.escape(text)}</p>', KO)
    footer(p, option, 2, total)

    p = page(doc, FOREST)
    label(p, fitz.Rect(48, 35, 300, 58), "CATEGORY COMPARISON", light=True)
    headline(p, fitz.Rect(48, 65, 746, 112), "용도에 맞춰 비교하는 제품 구성", "BUBR식 매트릭스의 장점만 취하고, 한 페이지 정보량을 네 제품군으로 제한했습니다.", light=True, size=25)
    comparisons = [
        ("져키", "고기가득 · 영양가득 · 베리가득", "대용량과 소용량", "meat"),
        ("덴탈", "치카하개", "240 g · 30개", "dental"),
        ("베이크드", "굽빵", "1 kg · 200 g", "baked"),
        ("시리얼", "멍스 · 프레쉬링", "100 g", "fresh"),
    ]
    for i, (category, names, pack, key) in enumerate(comparisons):
        x = 48 + i * 187
        p.draw_rect(fitz.Rect(x, 150, x + 169, 486), radius=0.025, color=None, fill=GREEN)
        add_image_fit(p, fitz.Rect(x + 10, 164, x + 159, 300), PRODUCT_IMAGES[key])
        add_html(p, fitz.Rect(x + 16, 325, x + 153, 464), f'<p style="font-size:8pt;color:#d8b36a;font-weight:700">0{i + 1}</p><p style="font-size:15pt;color:#ffffff;font-weight:700;margin-top:7pt">{category}</p><p style="font-size:8pt;color:#dce2dc;line-height:1.45;margin-top:10pt">{html.escape(names)}</p><p style="font-size:9pt;color:#d8b36a;font-weight:700;margin-top:12pt">{html.escape(pack)}</p>', KO, scale_low=0.82)
    footer(p, option, 3, total, light=True)

    p = page(doc)
    label(p, fitz.Rect(48, 35, 300, 58), "ORDER FLOW")
    headline(p, fitz.Rect(48, 65, 746, 112), "거래 검토는 네 단계로", "불명확한 조건은 추정하지 않고 상담 항목으로 분리합니다.", size=25)
    steps = [("01", "제품 선택", "제품군·포장 단위 확인"), ("02", "거래 상담", "MOQ·공급가·마진 확인"), ("03", "납기 확인", "가능 품목·리드타임 협의"), ("04", "발주 진행", "거래 형태에 맞춰 확정")]
    for i, (num, title, body) in enumerate(steps):
        x = 48 + i * 187
        p.draw_line(fitz.Point(x, 160), fitz.Point(x + 160, 160), color=GOLD, width=1.2)
        add_html(p, fitz.Rect(x, 178, x + 160, 295), f'<p style="font-size:20pt;color:#d8b36a;font-weight:700">{num}</p><p style="font-size:14pt;font-weight:700;margin-top:9pt">{title}</p><p style="font-size:8.3pt;line-height:1.45;color:#506056;margin-top:10pt">{body}</p>', KO)
    p.draw_rect(fitz.Rect(48, 370, 794, 505), radius=0.025, color=None, fill=FOREST)
    add_html(p, fitz.Rect(75, 394, 755, 480), '<p style="font-size:17pt;color:#ffffff;font-weight:700">B2B 거래 문의</p><p style="font-size:9pt;color:#dce2dc;margin-top:10pt">제로랩스 도매몰 · bldh2025@naver.com · KakaoTalk Channel</p><p style="font-size:8pt;color:#d8b36a;font-weight:700;margin-top:13pt">제품별 상세 사양과 거래 조건은 공식 채널에서 확인합니다.</p>', KO)
    footer(p, option, 4, total)
    return set_meta(doc, option, "Product brochure concept B")


def product_option_c() -> fitz.Document:
    """Ingredient and product story: warm editorial explanation plus products."""
    doc = fitz.open()
    c = PRODUCT_CONTENT[KO]
    company = COMPANY_CONTENT[KO]
    total = 4
    option = "제품소개서 C · 원료·제품 스토리"

    p = page(doc)
    add_image_cover(p, fitz.Rect(0, 0, 842, 595), ASSETS / "approach_remove.webp", opacity=0.18)
    p.draw_rect(fitz.Rect(0, 0, 842, 595), color=None, fill=CREAM, fill_opacity=0.22, overlay=True)
    add_logo(p, "zero", fitz.Rect(52, 42, 188, 104))
    label(p, fitz.Rect(52, 168, 480, 193), "PRODUCT STORY · OPTION C")
    headline(p, fitz.Rect(52, 208, 610, 380), "제품 이름보다 먼저\n왜 이 라인인지 설명합니다.", "간식 유형과 포장 단위를 원료 이미지·제품 사진·짧은 설명으로 이어 주는 스토리형 안", size=35)
    footer(p, option, 1, total)

    p = page(doc)
    label(p, fitz.Rect(48, 35, 300, 58), "PRODUCT PRINCIPLES")
    headline(p, fitz.Rect(48, 65, 746, 112), "제품을 이해하는 세 가지 기준", "검증되지 않은 효능 대신, 현재 공개 가능한 운영 원칙과 제품 정보를 사용합니다.", size=25)
    assets = ("approach_remove.webp", "approach_balance.webp", "make_supply.webp")
    for i, ((title, body), asset) in enumerate(zip(company["principles"], assets)):
        y = 150 + i * 124
        add_image_cover(p, fitz.Rect(48, y, 245, y + 108), ASSETS / asset)
        add_html(p, fitz.Rect(278, y + 7, 335, y + 45), f'<p style="font-size:18pt;color:#d8b36a;font-weight:700">0{i + 1}</p>', KO)
        add_html(p, fitz.Rect(350, y + 5, 520, y + 52), f'<p style="font-size:15pt;font-weight:700">{html.escape(title)}</p>', KO)
        add_html(p, fitz.Rect(540, y + 3, 794, y + 82), f'<p style="font-size:8.7pt;line-height:1.5;color:#506056">{html.escape(body)}</p>', KO)
    footer(p, option, 2, total)

    p = page(doc, FOREST)
    label(p, fitz.Rect(48, 35, 300, 58), "THREE PRODUCT FAMILIES", light=True)
    headline(p, fitz.Rect(48, 65, 746, 112), "형태가 다르면 제안 방식도 달라집니다", "져키·덴탈·베이크드/시리얼을 각각 다른 상품군으로 읽게 하는 구성", light=True, size=25)
    families = [
        ("져키", "육류·영양·베리 라인", "meat", c["products"]["meat_1kg"][1]),
        ("덴탈", "치카하개 240 g", "dental", c["products"]["dental"][1]),
        ("베이크드·시리얼", "굽빵 · 멍스 · 프레쉬링", "baked", c["products"]["baked_1kg"][1]),
    ]
    for i, (title, names, key, body) in enumerate(families):
        x = 48 + i * 249
        add_image_fit(p, fitz.Rect(x, 145, x + 229, 320), PRODUCT_IMAGES[key])
        add_html(p, fitz.Rect(x, 344, x + 229, 480), f'<p style="font-size:8pt;color:#d8b36a;font-weight:700">0{i + 1}</p><p style="font-size:15pt;color:#ffffff;font-weight:700;margin-top:7pt">{title}</p><p style="font-size:8.5pt;color:#d8b36a;font-weight:700;margin-top:8pt">{html.escape(names)}</p><p style="font-size:7.8pt;line-height:1.45;color:#dce2dc;margin-top:9pt">{html.escape(body)}</p>', KO, scale_low=0.82)
    footer(p, option, 3, total, light=True)

    p = page(doc)
    label(p, fitz.Rect(48, 35, 300, 58), "SELECTED PRODUCTS")
    headline(p, fitz.Rect(48, 65, 746, 112), "세 제품을 실제 크기로 비교", "카드 높이는 설명 분량만큼만 사용하고, 사진이 남은 공간을 차지합니다.", size=25)
    selected = [("dental", "dental"), ("berry_400g", "berry"), ("baked_200g", "baked")]
    for i, (item_key, image_key) in enumerate(selected):
        item = c["products"][item_key]
        x = 48 + i * 249
        p.draw_rect(fitz.Rect(x, 145, x + 229, 486), radius=0.025, color=(0.88, 0.84, 0.74), fill=WHITE, width=0.5)
        add_image_fit(p, fitz.Rect(x + 12, 158, x + 217, 318), PRODUCT_IMAGES[image_key])
        bullets = "".join(f'<li style="font-size:7.5pt;line-height:1.4;margin-bottom:2pt">{html.escape(value)}</li>' for value in item[2][:2])
        add_html(p, fitz.Rect(x + 16, 336, x + 213, 470), f'<p style="font-size:13pt;font-weight:700">{html.escape(item[0])}</p><p style="font-size:7.6pt;line-height:1.45;color:#506056;margin-top:7pt">{html.escape(item[1])}</p><ul style="padding-inline-start:13pt;margin-top:8pt">{bullets}</ul><p style="font-size:8.5pt;color:#a57d30;font-weight:700;margin-top:7pt">{html.escape(item[3])}</p>', KO, scale_low=0.8)
    footer(p, option, 4, total)
    return set_meta(doc, option, "Product brochure concept C")


def save_option(name: str, doc: fitz.Document) -> tuple[Path, list[Path]]:
    target = OUTPUT / f"{name}-ko-2026.pdf"
    save_with_language(doc, target, "ko-KR")
    rendered = render_pdf(target)
    preview = PREVIEWS / f"{name}-contact-sheet.png"
    contact_sheet(rendered, preview, columns=2)
    return target, rendered


def build() -> list[Path]:
    prepare_font_files()
    ensure_inputs()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    PREVIEWS.mkdir(parents=True, exist_ok=True)
    if TMP_CONCEPTS.exists():
        shutil.rmtree(TMP_CONCEPTS)
    TMP_CONCEPTS.mkdir(parents=True)

    builders = [
        ("company-option-a-homepage-editorial", company_option_a),
        ("company-option-b-sales-proof", company_option_b),
        ("company-option-c-brand-storybook", company_option_c),
        ("product-option-a-visual-catalog", product_option_a),
        ("product-option-b-buyer-specbook", product_option_b),
        ("product-option-c-ingredient-story", product_option_c),
    ]
    outputs: list[Path] = []
    overview_images: list[Path] = []
    for name, builder in builders:
        target, rendered = save_option(name, builder())
        outputs.append(target)
        overview_images.extend(rendered)
    contact_sheet(overview_images, PREVIEWS / "brochure-concepts-all-pages.png", columns=4)
    return outputs


if __name__ == "__main__":
    for output in build():
        print(output.relative_to(ROOT))

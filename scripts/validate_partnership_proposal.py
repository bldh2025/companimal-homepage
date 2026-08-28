#!/usr/bin/env python3
"""Validate the external-send ZERO LABS B2B partnership proposal PDF."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import fitz
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PDF = ROOT / "output/pdf/zerolabs-b2b-partnership-proposal-ko-2026.pdf"
REFERENCE_JSON = ROOT / "output/proposal/zerolabs-b2b-sku-commercial-reference-2026-08-28.json"
EXPECTED_HEADINGS = [
    "검토에서 첫 발주까지",
    "어떤 제품으로 시작하고",
    "제로랩스의 현재",
    "리뷰가 쌓인 대표 제품",
    "져키와 함께 구성하기 좋은",
    "두 가지 첫 발주 구성",
    "제품별 박스 입수",
    "실제 남는 금액",
    "역할과 연락 순서",
    "다음 발주를 결정",
    "첫 발주 전에",
    "파일럿 시작 여부를 결정",
]
REQUIRED_TEXT = [
    "유통 파트너사 귀중",
    "주식회사 반려동행",
    "266-88-03624",
    "2026.08.28",
    "현재 판매가",
    "견적 시 확정",
    "혼합 구성·1종",
    "판매소진율",
    "기여이익률",
    "품질·리콜",
    "거래 문의",
    "ceo@companimal.kr",
    "010-6540-7787",
    "가격과 거래 조건은 최종 견적서와 공급계약서를 기준으로 합니다",
    "가격과 재고는 주문 시점에 달라질 수 있습니다.",
    "VAT·배송·결제 조건은 견적서에서 안내드립니다.",
    "세부 역할과 반품 기준은 공급계약에서 확정합니다.",
]
FORBIDDEN_TEXT = [
    "WARDROBE",
    "CPS",
    "포스트백",
    "쿠키 추적",
    "AI 생성 참고 이미지",
    "내부 확인 필요",
    "자료 확인 필요",
    "32,757명이 선택",
    "당일 출고",
    "업계 최고 마진",
    "안 팔리면 반품",
    "100% 국내산 원료",
    "알러지 걱정 없는",
    "미트리스 3종",
    "8g×30",
    "VERSION 2.0",
    "본 자료는",
    "공통 외부 제안본",
    "회사 제공 판매채널",
    "확대 해석하지 않습니다",
    "제품소개서와",
    "공식 판매면에 확인되는",
    "질병·알레르기",
    "치료 또는 예방",
    "생성 이미지",
    "EVIDENCE & SOURCE LINKS",
    "증빙과 출처",
    "리뷰 집계 정의",
    "단순 합산한 의사결정",
    "마진을 약속하지 않습니다",
    "법적 구속력이 있는",
    "B2B 제휴와 주문 문의를 분리했습니다",
    "bldh2025@naver.com",
    "010-6532-4544",
    "공통 제안서",
]
REQUIRED_LINKS = {
    "mailto:ceo@companimal.kr",
    "tel:+821065407787",
    "https://companimal.kr/",
    "https://zerolabs.co.kr/",
    "https://pf.kakao.com/_xnyDcs",
}


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def comma_won(value: int) -> str:
    return f"{value:,}원"


def page_uris(reader: PdfReader) -> set[str]:
    uris: set[str] = set()
    for page in reader.pages:
        for annotation_ref in page.get("/Annots", []):
            annotation = annotation_ref.get_object()
            action = annotation.get("/A")
            if action:
                uri = action.get_object().get("/URI")
                if uri:
                    uris.add(str(uri))
    return uris


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", nargs="?", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    pdf_path = args.pdf.resolve()
    assert_true(pdf_path.is_file(), f"PDF not found: {pdf_path}")
    assert_true(REFERENCE_JSON.is_file(), f"SKU reference is missing: {REFERENCE_JSON}")
    reference = json.loads(REFERENCE_JSON.read_text(encoding="utf-8"))
    assert_true(reference.get("contacts") == {"inquiries": {"email": "ceo@companimal.kr", "phone": "010-6540-7787"}}, "Contact reference must use the canonical inquiry email and phone")

    reader = PdfReader(str(pdf_path))
    assert_true(not reader.is_encrypted, "PDF must not be encrypted")
    assert_true(len(reader.pages) == 12, f"Expected 12 pages, found {len(reader.pages)}")
    metadata = reader.metadata
    assert_true(metadata and metadata.title == "ZERO LABS B2B 파트너십 제안서 2026", f"Unexpected title: {metadata.title if metadata else None}")
    root = reader.trailer["/Root"]
    assert_true(root.get("/OpenAction") is None, "PDF contains OpenAction")
    assert_true(root.get("/Names") is None or root.get("/Names").get_object().get("/JavaScript") is None, "PDF contains JavaScript")
    assert_true(root.get("/Names") is None or root.get("/Names").get_object().get("/EmbeddedFiles") is None, "PDF contains embedded files")
    assert_true(root.get("/StructTreeRoot") is not None, "PDF is missing a structure tree")
    assert_true(str(root.get("/Lang")) == "ko-KR", f"Unexpected PDF language: {root.get('/Lang')}")

    doc = fitz.open(pdf_path)
    assert_true(doc.page_count == 12, f"PyMuPDF page count differs: {doc.page_count}")
    pages_text: list[str] = []
    page_images: list[int] = []
    font_sizes: list[float] = []
    for index, page in enumerate(doc):
        rect = page.rect
        assert_true(abs(rect.width - 960) < 1.5 and abs(rect.height - 540) < 1.5, f"Page {index + 1} is not 16:9: {rect}")
        text = page.get_text("text").strip()
        assert_true(len(text) >= 100, f"Page {index + 1} has too little searchable text: {len(text)} chars")
        assert_true(EXPECTED_HEADINGS[index] in text, f"Page {index + 1} missing expected heading: {EXPECTED_HEADINGS[index]}")
        pages_text.append(text)
        page_images.append(len(page.get_images(full=True)))
        page_dict = page.get_text("dict")
        for block in page_dict.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    if span.get("text", "").strip():
                        font_sizes.append(float(span["size"]))

    all_text = "\n".join(pages_text)
    for text in REQUIRED_TEXT:
        assert_true(text in all_text, f"Missing required text: {text}")
    for text in FORBIDDEN_TEXT:
        assert_true(text not in all_text, f"Forbidden legacy/unsupported text remains: {text}")
    assert_true(page_images[0] >= 1, "Cover must include a hero image")
    assert_true(page_images[3] >= 4 and page_images[4] >= 4, "Product pages must include all eight product images")
    assert_true(min(font_sizes) >= 9.8, f"PDF contains text smaller than 10pt: {min(font_sizes):.2f}pt")

    for review_text in ("32,757", "11,659", "10,906", "6,473", "31,169", "1,588"):
        assert_true(review_text in all_text, f"Review evidence is missing: {review_text}")
    assert_true("미트리스" in pages_text[4] and "혼합 구성·1종" in pages_text[4] and "3종" not in pages_text[4].split("미트리스", 1)[1].split("멍스", 1)[0], "Meatless must be one mixed configuration")

    commercial_page = pages_text[6]
    for sku in reference["public_b2b_skus"]:
        for value in (sku["product"], sku["pack"], f"{sku['case_quantity']}개", comma_won(sku["box_price_krw"]), comma_won(sku["unit_reference_krw"])):
            assert_true(value in commercial_page, f"Commercial reference is missing {sku['id']}: {value}")
    scenario_page = pages_text[5]
    for scenario in reference["starter_scenarios"]:
        assert_true(f"{scenario['units']}개" in scenario_page, f"Starter scenario units missing: {scenario['id']}")
        assert_true(comma_won(scenario["public_display_total_krw"]) in scenario_page, f"Starter scenario total missing: {scenario['id']}")

    for formula in ("실판매수량 × (VAT 포함 실제 판매가 ÷ 1.1)", "VAT 별도 박스 공급가액 ÷ 박스 입수량", "기여이익 ÷ VAT 제외 순매출 × 100"):
        assert_true(formula in pages_text[7], f"Economics formula missing: {formula}")
    for formula in ("실판매수량 ÷ 입고수량", "기말재고 ÷ 최근 주평균 판매수량", "승인 반품·불량수량 ÷ 출고수량"):
        assert_true(formula in pages_text[9], f"Pilot KPI formula missing: {formula}")

    uris = page_uris(reader)
    assert_true(len(uris) >= 7, f"Expected at least 7 clickable URI targets, found {len(uris)}: {sorted(uris)}")
    for target in REQUIRED_LINKS:
        assert_true(target in uris, f"Missing clickable PDF URI: {target}")
    assert_true(any("xn--" in uri and "/category/" in uri for uri in uris), f"Missing clickable B2B category URI: {sorted(uris)}")

    result = {
        "status": "ok",
        "pages": doc.page_count,
        "bytes": pdf_path.stat().st_size,
        "sha256": hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
        "title": metadata.title,
        "page_images": page_images,
        "min_font_pt": round(min(font_sizes), 2),
        "clickable_uri_count": len(uris),
        "output": str(pdf_path),
    }
    print(json.dumps(result, ensure_ascii=False) if args.json else json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

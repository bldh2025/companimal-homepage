#!/usr/bin/env python3
"""Validate the external-send ZERO LABS CPS partnership proposal PDF."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import fitz
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PDF = ROOT / "output/pdf/zerolabs-b2b-partnership-proposal-ko-2026.pdf"
REFERENCE_JSON = ROOT / "output/proposal/zerolabs-b2b-sku-commercial-reference-2026-08-28.json"
EXPECTED_HEADINGS = [
    "노출에서 구매까지",
    "지면은 파트너사가",
    "제품과 소비자 반응",
    "8개 제품군에 쌓인 리뷰",
    "첫 콘텐츠를 구성",
    "콘텐츠 주제를 넓힙니다",
    "여러 고객 접점",
    "CPS 파트너십 구조",
    "CPS 고객 및 데이터 흐름",
    "어떤 주문을 파트너 성과",
    "클릭부터 성과 인정 매출",
    "수수료는 성과가 인정된",
    "구매 이유를 만듭니다",
    "CPS 제휴를 시작",
    "정산 프로세스",
    "역할 분담 및 운영체계",
    "CPS 운영안을 함께",
]
REQUIRED_TEXT = [
    "CPS",
    "제휴 파트너사 귀중",
    "주식회사 반려동행",
    "266-88-03624",
    "2026.08.28",
    "2026.08.27",
    "32,757건",
    "노출과 클릭에는 비용이 발생하지 않습니다",
    "성과 인정 판매",
    "전용 링크",
    "파트너 코드",
    "ZERO LABS 공식몰",
    "취소·반품·환불",
    "성과 인정 매출액",
    "합의된 수수료율",
    "정산서",
    "세금계산서",
    "개인정보",
    "경제적 이해관계",
    "협의 후 확정",
    "제휴계약서",
    "ceo@companimal.kr",
    "010-6540-7787",
]
FORBIDDEN_TEXT = [
    "WARDROBE",
    "DISTRIBUTION PARTNER",
    "유통 파트너",
    "B2B",
    "첫 발주",
    "발주",
    "4박스",
    "박스 판매가",
    "박스 입수",
    "개당 환산가",
    "공급가",
    "매입",
    "매입가",
    "견적",
    "공급계약",
    "입고수량",
    "판매소진율",
    "재고주수",
    "기여이익",
    "마진",
    "재주문",
    "B2B몰",
    "도매",
    "총판",
    "수익성 계산",
    "840,000원",
    "993,600원",
    "1,397,100원",
    "222,500원",
    "최대 3%",
    "포스트백",
    "실시간 대시보드",
    "API",
    "AI 생성 참고 이미지",
    "생성 이미지",
    "제품소개서와",
    "질병·알레르기",
    "치료 또는 예방",
    "bldh2025@naver.com",
    "010-6532-4544",
    "제로랩스.com",
]
REQUIRED_LINKS = {
    "mailto:ceo@companimal.kr",
    "tel:+821065407787",
    "https://companimal.kr/",
    "https://zerolabs.co.kr/",
    "https://pf.kakao.com/_xnyDcs",
}
REQUIRED_TBD_IDS = {
    "commission_rate",
    "commission_base",
    "discount_handling",
    "attribution_method",
    "attribution_window",
    "overlap_priority",
    "confirmation_point",
    "cancellation_refund",
    "settlement_schedule",
    "vat",
    "tax_evidence",
    "minimum_payout",
    "reward_funding",
    "personal_data",
    "reporting",
    "placement",
    "asset_usage",
    "cs_scope",
    "incident_response",
    "contract",
}


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


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


def assert_ordered(text: str, markers: tuple[str, ...], label: str) -> None:
    positions = [text.find(marker) for marker in markers]
    assert_true(all(position >= 0 for position in positions), f"{label} is missing flow markers: {markers}")
    assert_true(positions == sorted(positions), f"{label} flow order is wrong: {list(zip(markers, positions))}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", nargs="?", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    pdf_path = args.pdf.resolve()
    assert_true(pdf_path.is_file(), f"PDF not found: {pdf_path}")
    assert_true(REFERENCE_JSON.is_file(), f"CPS reference is missing: {REFERENCE_JSON}")
    reference = json.loads(REFERENCE_JSON.read_text(encoding="utf-8"))

    assert_true(reference.get("schema_version") == 2, "CPS reference schema must be version 2")
    assert_true(reference.get("contacts") == {"inquiries": {"email": "ceo@companimal.kr", "phone": "010-6540-7787"}}, "Contact reference must use the canonical inquiry email and phone")
    assert_true(reference.get("company", {}).get("business_registration_number") == "266-88-03624", "Company registration number differs")
    review = reference.get("review_snapshot", {})
    assert_true(review.get("total") == review.get("coupang", 0) + review.get("other_channels", 0), "Review channel totals differ")
    assert_true(review.get("total") == sum(item.get("reviews", 0) for item in review.get("products", [])), "Product review totals differ")
    model = reference.get("cps_model", {})
    assert_true(model.get("type") == "CPS", "Model must be CPS")
    assert_true(model.get("partner_inventory_purchase") is False, "CPS partner must not purchase inventory")
    assert_true(model.get("exposure_click_fee") is False, "Exposure and clicks must not incur fees")
    assert_true(model.get("commission_trigger") == "성과 인정 판매", "Commission trigger must be recognized sales")
    assert_true(model.get("formula") == "성과 인정 매출액 × 합의된 수수료율 = 수수료", "Commission formula differs")
    unresolved = reference.get("unresolved_terms", [])
    assert_true({item.get("id") for item in unresolved} == REQUIRED_TBD_IDS, "CPS unresolved term set differs")
    assert_true(all(item.get("status") == "tbd" for item in unresolved), "All unresolved CPS terms must remain tbd")
    assert_true(not any(key in reference for key in ("public_b2b_skus", "starter_scenarios", "commercial_guardrails")), "Wholesale reference keys remain")

    reader = PdfReader(str(pdf_path))
    assert_true(not reader.is_encrypted, "PDF must not be encrypted")
    assert_true(len(reader.pages) == 17, f"Expected 17 pages, found {len(reader.pages)}")
    metadata = reader.metadata
    assert_true(metadata and metadata.title == "ZERO LABS CPS 파트너십 제안서 2026", f"Unexpected title: {metadata.title if metadata else None}")
    root = reader.trailer["/Root"]
    assert_true(root.get("/OpenAction") is None, "PDF contains OpenAction")
    assert_true(root.get("/Names") is None or root.get("/Names").get_object().get("/JavaScript") is None, "PDF contains JavaScript")
    assert_true(root.get("/Names") is None or root.get("/Names").get_object().get("/EmbeddedFiles") is None, "PDF contains embedded files")
    assert_true(root.get("/StructTreeRoot") is not None, "PDF is missing a structure tree")
    assert_true(str(root.get("/Lang")) == "ko-KR", f"Unexpected PDF language: {root.get('/Lang')}")

    doc = fitz.open(pdf_path)
    assert_true(doc.page_count == 17, f"PyMuPDF page count differs: {doc.page_count}")
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
    for required in REQUIRED_TEXT:
        assert_true(required in all_text, f"Missing required text: {required}")
    for forbidden in FORBIDDEN_TEXT:
        assert_true(forbidden not in all_text, f"Forbidden wholesale/unsupported text remains: {forbidden}")
    assert_true(re.search(r"\d+(?:\.\d+)?\s*%", all_text) is None, "Unapproved commission percentage remains")
    assert_true(page_images[0] >= 1, "Cover must include a hero image")
    assert_true(page_images[4] >= 4 and page_images[5] >= 4, "Product pages must include all eight product images")
    assert_true(min(font_sizes) >= 9.8, f"PDF contains text smaller than 10pt: {min(font_sizes):.2f}pt")

    for item in review["products"]:
        assert_true(item["product"] in pages_text[3] and f"{item['reviews']:,}" in pages_text[3], f"Review snapshot is missing: {item}")
    for page_number in (9, 10, 11, 12, 14, 15, 16, 17):
        assert_true("협의 후 확정" in pages_text[page_number - 1], f"Page {page_number} must keep unresolved terms explicit")

    assert_ordered(pages_text[7], ("노출·클릭", "구매 발생", "구매 확정"), "CPS structure")
    assert_ordered(pages_text[8], ("전용 링크 클릭", "상품 탐색·구매", "취소·반품·환불 반영", "수수료 정산"), "Customer/data")
    settlement_flow = pages_text[14].split("01", 1)[1]
    assert_ordered(settlement_flow, ("주문 발생", "예상 실적 집계", "취소·반품·환불 반영", "성과 확정", "정산서 확인", "세금계산서", "수수료 지급"), "Settlement")
    assert_true("성과 인정 매출액" in pages_text[11] and "합의된 수수료율" in pages_text[11], "Commission formula is missing from page 12")
    assert_true("파트너사" in pages_text[15] and "ZERO LABS" in pages_text[15] and "개인정보" in pages_text[15], "R&R page is incomplete")

    uris = page_uris(reader)
    assert_true(len(uris) >= 5, f"Expected at least 5 clickable URI targets, found {len(uris)}: {sorted(uris)}")
    for target in REQUIRED_LINKS:
        assert_true(target in uris, f"Missing clickable PDF URI: {target}")
    assert_true(not any("xn--" in uri or "category/" in uri for uri in uris), f"Wholesale B2B URI remains: {sorted(uris)}")

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

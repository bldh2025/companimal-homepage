#!/usr/bin/env python3
"""Embed and lay out the approved reference images in the company profile."""

from __future__ import annotations

import base64
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPANY_PROFILE = ROOT / "output" / "brochure" / "zerolabs-company-profile-ko-2026.html"
PROVENANCE_PATH = ROOT / "zerolabs_homepage_assets" / "company-profile" / "PROVENANCE.json"
CONTACT_PHONE = "010-6540-7787"
MAX_REFERENCE_IMAGE_BYTES = 320_000

FACTORY_IMAGE_SPECS = {
    "bda48612-b5bf-4580-8be2-1c300f2df5e8": {
        "path": "zerolabs_homepage_assets/company-profile/oem-production-ai-v1.jpg",
        "sha256": "174d5b31170cc8ebb6fc2a97cfe0c40aeb0620569808b8e02482b1b1be8fbfd5",
        "alt": "국내 제조 공정을 표현한 이미지",
    },
    "438f4683-da95-4036-a9c3-80d9fc5f71ac": {
        "path": "zerolabs_homepage_assets/company-profile/ingredient-inspection-ai-v1.jpg",
        "sha256": "7f0623d745e8fc855207bc00051222f9f9650da3b559ab1297e1cb28e9b0c3c5",
        "alt": "국내산 원료 검수 과정을 표현한 이미지",
    },
    "765443f2-9adf-427a-a7c1-748d4d0fd972": {
        "path": "zerolabs_homepage_assets/company-profile/packing-dispatch-ai-v1.jpg",
        "sha256": "b58611b15adb21f888dfcfdcf51ed1c7383df00d2679e29c514f2c57a6fd1f21",
        "alt": "일관된 포장·출하 과정을 표현한 이미지",
    },
}

PRINCIPLE_IMAGE_SPECS = {
    "947d3d77-9af4-4457-89ff-956f7a05d96a": {
        "path": "zerolabs_homepage_assets/company-profile/principle-remove-ai-v1.jpg",
        "sha256": "90c9f01fd304295127a427d69739f25568a77214312bb213ed14cf5d133964ce",
        "alt": "불필요한 요소를 덜어낸 간식 설계 원칙 이미지",
    },
    "b088532b-c297-4e78-950c-97a277a371a6": {
        "path": "zerolabs_homepage_assets/company-profile/principle-balance-ai-v1.jpg",
        "sha256": "4210de7dc30e3b73efb07009300ba32cafe42366c35fd8dc7663175dcbb25c4a",
        "alt": "여러 원료 구성 요소를 나누어 담은 균형 설계 이미지",
    },
    "4170fae5-51dd-4a46-9262-a2378f39a524": {
        "path": "zerolabs_homepage_assets/company-profile/principle-supply-ai-v1.jpg",
        "sha256": "5d82b27eb1d1429d26b103f251873d905557f04e6d67a2814d1dcc59f56c416f",
        "alt": "동일한 규격의 포장 단위를 정렬한 공급 구조 이미지",
    },
}

REFERENCE_IMAGE_SPECS = {**FACTORY_IMAGE_SPECS, **PRINCIPLE_IMAGE_SPECS}

PRINCIPLE_CARDS = (
    (
        "947d3d77-9af4-4457-89ff-956f7a05d96a",
        "Remove",
        "덜어내다",
        "인공첨가물과 불필요한 성분을 줄여, 반려견이 매일 먹어도 부담이 적은 간식을 지향합니다.",
    ),
    (
        "b088532b-c297-4e78-950c-97a277a371a6",
        "Balance",
        "조합하다",
        "육류·채소·과일·기능성 원료를 목적에 맞게 조합하여 균형 잡힌 레시피를 설계합니다.",
    ),
    (
        "4170fae5-51dd-4a46-9262-a2378f39a524",
        "Supply",
        "공급하다",
        "B2B 거래처가 안정적으로 운영할 수 있는 공급 구조를 갖추어 지속 가능한 판매를 돕습니다.",
    ),
)

MANIFEST_RE = re.compile(
    r'(<script type="__bundler/manifest">\s*)(.*?)(\s*</script>)', re.S
)
TEMPLATE_RE = re.compile(
    r'(<script type="__bundler/template">\s*)(.*?)(\s*</script>)', re.S
)


def replace_payload(source: str, pattern: re.Pattern[str], payload: str) -> str:
    match = pattern.search(source)
    if not match:
        raise RuntimeError("Company profile bundle payload is missing")
    return source[: match.start(2)] + payload + source[match.end(2) :]


def normalize_factory_image_card(template: str, asset_id: str, alt: str) -> str:
    pattern = re.compile(
        r'<div style="flex:1; min-height:56px; overflow:hidden; display:flex'
        r'(?:; position:relative)?;">'
        r'<img\b[^>]*\bsrc="'
        + re.escape(asset_id)
        + r'"[^>]*>'
        r'(?:<span data-ai-image-label="'
        + re.escape(asset_id)
        + r'"[^>]*>.*?</span>)?'
        r'</div>',
        re.S,
    )
    replacement = (
        '<div style="flex:1; min-height:56px; overflow:hidden; display:flex;">'
        f'<img src="{asset_id}" alt="{alt}" '
        'style="width:100%; height:100%; object-fit:cover; display:block;" '
        f'data-ai-image="{asset_id}"></div>'
    )
    template, count = pattern.subn(lambda _: replacement, template)
    if count != 1:
        raise RuntimeError(f"Company profile image card structure changed: {asset_id}")
    return template


def build_principle_section() -> str:
    cards: list[str] = []
    for asset_id, english, korean, body in PRINCIPLE_CARDS:
        alt = str(PRINCIPLE_IMAGE_SPECS[asset_id]["alt"])
        cards.append(
            f'''      <div data-principle-card="{english.lower()}" style="background:#fbfcf9; color:#1f3325; padding:0; overflow:hidden; display:flex; flex-direction:column;">
        <div data-principle-image-card="{english.lower()}" style="height:372px; overflow:hidden; display:flex; flex:none;"><img src="{asset_id}" alt="{alt}" style="width:100%; height:100%; object-fit:cover; display:block;" data-ai-image="{asset_id}"></div>
        <div style="padding:30px 32px 34px; display:flex; flex-direction:column; gap:18px;">
          <div style="display:flex; align-items:baseline; gap:16px; white-space:nowrap;"><span style="font-size:40px; font-weight:600;">{english}</span><span style="font-size:30px; color:#5b6b5e;">{korean}</span></div>
          <p style="margin:0; font-size:26px; line-height:1.62; font-weight:300; color:#4c5c50;">{body}</p>
        </div>
      </div>
'''
        )
    return f'''<section data-label="04 브랜드 원칙" data-screen-label="04" data-speaker-notes="Remove · Balance · Supply 3원칙." style="background:#1f3325; color:#f8faf5; font-family:'IBM Plex Sans KR',sans-serif; padding:84px 96px; box-sizing:border-box; display:flex; flex-direction:column; gap:44px;">
    <div style="display:flex; justify-content:space-between; align-items:flex-end; gap:64px; flex:none;">
      <div style="display:flex; flex-direction:column; gap:18px;">
        <h2 style="margin:0; font-size:62px; font-weight:600; letter-spacing:-0.025em; line-height:1.18;">제로랩스가 간식을 만드는 세 가지 원칙</h2>
        <p style="margin:0; font-size:29px; line-height:1.65; font-weight:300; color:#cfdcd2; max-width:1100px;">불필요한 것은 덜어내고, 필요한 것은 목적에 맞게 조합하며, 파트너가 안정적으로 운영할 수 있는 구조를 만듭니다.</p>
      </div>
      <span style="font-size:24px; letter-spacing:0.18em; color:#9dbaa5; white-space:nowrap; flex:none;">02 — APPROACH</span>
    </div>
    <div style="flex:1; display:grid; grid-template-columns:repeat(3,1fr); gap:28px;">
{''.join(cards)}    </div>
  </section>'''


def replace_principle_section(template: str) -> str:
    pattern = re.compile(
        r'<section\b[^>]*data-label="04 브랜드 원칙".*?</section>', re.S
    )
    template, count = pattern.subn(lambda _: build_principle_section(), template)
    if count != 1:
        raise RuntimeError("Company profile principle section is missing or duplicated")
    return template


def strip_decorative_ordinals(template: str) -> str:
    product_match = re.search(
        r'<section\b[^>]*data-label="06 제품 라인업".*?</section>', template, re.S
    )
    if not product_match:
        raise RuntimeError("Company profile product lineup section is missing")
    product_section = product_match.group(0)
    product_pattern = re.compile(
        r'<div style="display:flex; justify-content:space-between; align-items:baseline; flex:none;">'
        r'<span style="font-size:24px; color:#3f6b4a;">0[1-8]</span>'
        r'(<span style="font-size:24px; color:#5b6b5e; white-space:nowrap;">[^<]+</span>)'
        r'</div>'
    )
    product_replacement = (
        '<div style="display:flex; justify-content:flex-end; '
        'align-items:baseline; flex:none;">\\1</div>'
    )
    product_section, product_count = product_pattern.subn(product_replacement, product_section)
    if product_count not in (0, 8):
        raise RuntimeError(f"Company profile product ordinal count is {product_count}, expected 0 or 8")
    product_type_rows = product_section.count(
        'justify-content:flex-end; align-items:baseline; flex:none;">'
        '<span style="font-size:24px; color:#5b6b5e; white-space:nowrap;">'
    )
    if product_type_rows != 8:
        raise RuntimeError(f"Company profile product type row count is {product_type_rows}, expected 8")
    template = template[: product_match.start()] + product_section + template[product_match.end() :]

    partnership_match = re.search(
        r'<section\b[^>]*data-label="09 파트너십".*?</section>', template, re.S
    )
    if not partnership_match:
        raise RuntimeError("Company profile partnership section is missing")
    partnership_section = partnership_match.group(0)
    partnership_pattern = re.compile(
        r'\s*<span style="font-size:26px; color:#3f6b4a;">0[1-3]</span>'
    )
    partnership_section, partnership_count = partnership_pattern.subn("", partnership_section)
    if partnership_count not in (0, 3):
        raise RuntimeError(f"Company profile partnership ordinal count is {partnership_count}, expected 0 or 3")
    for title in ("제품력", "설명력", "재구매 구조"):
        if partnership_section.count(f'<div style="font-size:46px; font-weight:600;">{title}</div>') != 1:
            raise RuntimeError(f"Company profile partnership card is missing: {title}")
    template = (
        template[: partnership_match.start()]
        + partnership_section
        + template[partnership_match.end() :]
    )
    return template


def reposition_contents_heading(template: str) -> str:
    section_match = re.search(
        r'<section\b[^>]*data-label="02 목차".*?</section>', template, re.S
    )
    if not section_match:
        raise RuntimeError("Company profile contents section is missing")
    section = section_match.group(0)
    heading_pattern = re.compile(
        r'<div(?: data-contents-heading="top")? '
        r'style="display:flex; flex-direction:column; '
        r'justify-content:(?:space-between|flex-start)(?:; gap:18px)?;">\s*'
        r'(<span[^>]*>CONTENTS</span>)\s*'
        r'(<h2[^>]*>목차</h2>)\s*'
        r'</div>',
        re.S,
    )
    replacement = (
        '<div data-contents-heading="top" '
        'style="display:flex; flex-direction:column; justify-content:flex-start; gap:18px;">\n'
        '      \\1\n'
        '      \\2\n'
        '    </div>'
    )
    section, count = heading_pattern.subn(replacement, section)
    if count != 1:
        raise RuntimeError("Company profile contents heading structure changed")
    template = template[: section_match.start()] + section + template[section_match.end() :]
    return template


def ensure_contact_phone(template: str) -> str:
    section_match = re.search(
        r'<section\b[^>]*data-label="12 문의".*?</section>', template, re.S
    )
    if not section_match:
        raise RuntimeError("Company profile contact section is missing")
    section = section_match.group(0)
    homepage_row = (
        '<div style="display:flex; gap:40px; border-top:1px solid #33513b; '
        'padding:24px 0;"><span style="width:220px; font-size:26px; color:#9dbaa5;">'
        '홈페이지</span><span style="font-size:29px; font-weight:500;">companimal.kr</span></div>'
    )
    phone_row = (
        '<div data-contact-phone="true" style="display:flex; gap:40px; '
        'border-top:1px solid #33513b; border-bottom:1px solid #33513b; padding:24px 0;">'
        '<span style="width:220px; font-size:26px; color:#9dbaa5;">문의전화</span>'
        f'<span style="font-size:29px; font-weight:500;">{CONTACT_PHONE}</span></div>'
    )
    if section.count(phone_row) == 1:
        if section.count(homepage_row) != 1:
            raise RuntimeError("Company profile homepage row changed after phone insertion")
        return template
    legacy_homepage_pattern = re.compile(
        r'<div style="display:flex; gap:40px; border-top:1px solid #33513b; '
        r'border-bottom:1px solid #33513b; padding:24px 0;">'
        r'<span style="width:220px; font-size:26px; color:#9dbaa5;">홈페이지</span>'
        r'<span style="font-size:29px; font-weight:500;">companimal\.kr</span></div>'
    )
    section, count = legacy_homepage_pattern.subn(homepage_row + "\n        " + phone_row, section)
    if count != 1 or section.count(CONTACT_PHONE) != 1:
        raise RuntimeError("Company profile contact phone insertion failed")
    return template[: section_match.start()] + section + template[section_match.end() :]


def strip_visible_ai_disclosures(template: str) -> str:
    disclosure_pattern = re.compile(
        r'\s*<p data-ai-image-disclosure="(?:production|principle)-reference-images"'
        r'[^>]*>.*?</p>',
        re.S,
    )
    template, disclosure_count = disclosure_pattern.subn("", template)
    if disclosure_count not in (0, 1, 2):
        raise RuntimeError(
            f"Company profile disclosure count is {disclosure_count}, expected 0 to 2"
        )
    forbidden_patterns = (
        r"AI\s*(?:생성|사용)",
        r"인공지능",
        r"생성형",
        r"참고\s*이미지",
        r"촬영한\s*것이\s*아닙니다",
        r"실제\s*(?:시설|원료·시설)\s*아님",
    )
    remaining = [pattern for pattern in forbidden_patterns if re.search(pattern, template)]
    if remaining or "data-ai-image-disclosure=" in template or "data-ai-image-label=" in template:
        raise RuntimeError(f"Company profile still exposes AI reference copy: {remaining}")
    return template


def update_company_profile_bundle(path: Path = COMPANY_PROFILE) -> bool:
    source = path.read_text(encoding="utf-8")
    manifest_match = MANIFEST_RE.search(source)
    template_match = TEMPLATE_RE.search(source)
    if not manifest_match or not template_match:
        raise RuntimeError("Company profile bundler manifest/template is missing")
    manifest = json.loads(manifest_match.group(2))
    template = json.loads(template_match.group(2))

    for asset_id, spec in REFERENCE_IMAGE_SPECS.items():
        asset_path = ROOT / spec["path"]
        data = asset_path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != spec["sha256"]:
            raise RuntimeError(f"Reference image SHA-256 mismatch: {asset_path}")
        if len(data) > MAX_REFERENCE_IMAGE_BYTES:
            raise RuntimeError(f"Reference image exceeds size ceiling: {asset_path}")
        manifest[asset_id] = {
            "mime": "image/jpeg",
            "compressed": False,
            "data": base64.b64encode(data).decode("ascii"),
        }
        if asset_id in FACTORY_IMAGE_SPECS:
            template = normalize_factory_image_card(template, asset_id, str(spec["alt"]))

    template = replace_principle_section(template)
    template = strip_decorative_ordinals(template)
    template = reposition_contents_heading(template)
    template = ensure_contact_phone(template)
    template = strip_visible_ai_disclosures(template)
    manifest_payload = json.dumps(manifest, ensure_ascii=False, separators=(",", ":"))
    template_payload = json.dumps(template, ensure_ascii=False).replace("</", "<\\u002F")
    updated = replace_payload(source, MANIFEST_RE, manifest_payload)
    updated = replace_payload(updated, TEMPLATE_RE, template_payload)
    if updated == source:
        return False
    path.write_text(updated, encoding="utf-8")
    return True


def main() -> None:
    changed = update_company_profile_bundle()
    print(
        json.dumps(
            {
                "status": "ok",
                "changed": changed,
                "factory_images": len(FACTORY_IMAGE_SPECS),
                "principle_images": len(PRINCIPLE_IMAGE_SPECS),
            }
        )
    )


if __name__ == "__main__":
    main()

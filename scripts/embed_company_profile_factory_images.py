#!/usr/bin/env python3
"""Embed and lay out the approved AI reference images in the company profile."""

from __future__ import annotations

import base64
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPANY_PROFILE = ROOT / "output" / "brochure" / "zerolabs-company-profile-ko-2026.html"
PROVENANCE_PATH = ROOT / "zerolabs_homepage_assets" / "company-profile" / "PROVENANCE.json"
CARD_DISCLOSURE = "AI 생성 참고 이미지"
SECTION_DISCLOSURE_COLOR = "#4c5c50"
SECTION_DISCLOSURE = (
    "※ 생산·원료 이미지는 이해를 돕기 위한 AI 생성 참고 이미지이며, "
    "실제 자사 소유 시설 또는 특정 협력 제조 시설·원료·제품을 촬영한 것이 아닙니다."
)
PRINCIPLE_DISCLOSURE = (
    "※ 이 페이지의 이미지는 이해를 돕기 위한 AI 생성 참고 이미지이며, "
    "실제 원료·제품·거래처·시설을 촬영한 것이 아닙니다."
)
MAX_REFERENCE_IMAGE_BYTES = 320_000

FACTORY_IMAGE_SPECS = {
    "bda48612-b5bf-4580-8be2-1c300f2df5e8": {
        "path": "zerolabs_homepage_assets/company-profile/oem-production-ai-v1.jpg",
        "sha256": "174d5b31170cc8ebb6fc2a97cfe0c40aeb0620569808b8e02482b1b1be8fbfd5",
        "alt": "제조 공정을 표현한 AI 생성 참고 이미지(실제 시설 아님)",
    },
    "438f4683-da95-4036-a9c3-80d9fc5f71ac": {
        "path": "zerolabs_homepage_assets/company-profile/ingredient-inspection-ai-v1.jpg",
        "sha256": "7f0623d745e8fc855207bc00051222f9f9650da3b559ab1297e1cb28e9b0c3c5",
        "alt": "원료 검수를 표현한 AI 생성 참고 이미지(실제 원료·시설 아님)",
    },
    "765443f2-9adf-427a-a7c1-748d4d0fd972": {
        "path": "zerolabs_homepage_assets/company-profile/packing-dispatch-ai-v1.jpg",
        "sha256": "b58611b15adb21f888dfcfdcf51ed1c7383df00d2679e29c514f2c57a6fd1f21",
        "alt": "포장·출하를 표현한 AI 생성 참고 이미지(실제 시설 아님)",
    },
}

PRINCIPLE_IMAGE_SPECS = {
    "947d3d77-9af4-4457-89ff-956f7a05d96a": {
        "path": "zerolabs_homepage_assets/company-profile/principle-remove-ai-v1.jpg",
        "sha256": "90c9f01fd304295127a427d69739f25568a77214312bb213ed14cf5d133964ce",
        "alt": "불필요한 요소를 덜어낸 상태를 표현한 AI 생성 참고 이미지",
    },
    "b088532b-c297-4e78-950c-97a277a371a6": {
        "path": "zerolabs_homepage_assets/company-profile/principle-balance-ai-v1.jpg",
        "sha256": "4210de7dc30e3b73efb07009300ba32cafe42366c35fd8dc7663175dcbb25c4a",
        "alt": "여러 원료 구성 요소를 목적에 맞게 나누어 담은 AI 생성 참고 이미지",
    },
    "4170fae5-51dd-4a46-9262-a2378f39a524": {
        "path": "zerolabs_homepage_assets/company-profile/principle-supply-ai-v1.jpg",
        "sha256": "5d82b27eb1d1429d26b103f251873d905557f04e6d67a2814d1dcc59f56c416f",
        "alt": "동일한 규격의 포장 단위를 정렬한 공급 구조 AI 생성 참고 이미지",
    },
}

REFERENCE_IMAGE_SPECS = {**FACTORY_IMAGE_SPECS, **PRINCIPLE_IMAGE_SPECS}

PRINCIPLE_CARDS = (
    (
        "947d3d77-9af4-4457-89ff-956f7a05d96a",
        "01",
        "Remove",
        "덜어내다",
        "인공첨가물과 불필요한 성분을 줄여, 반려견이 매일 먹어도 부담이 적은 간식을 지향합니다.",
    ),
    (
        "b088532b-c297-4e78-950c-97a277a371a6",
        "02",
        "Balance",
        "조합하다",
        "육류·채소·과일·기능성 원료를 목적에 맞게 조합하여 균형 잡힌 레시피를 설계합니다.",
    ),
    (
        "4170fae5-51dd-4a46-9262-a2378f39a524",
        "03",
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
    for asset_id, number, english, korean, body in PRINCIPLE_CARDS:
        alt = str(PRINCIPLE_IMAGE_SPECS[asset_id]["alt"])
        cards.append(
            f'''      <div data-principle-card="{english.lower()}" style="background:#fbfcf9; color:#1f3325; padding:0; overflow:hidden; display:flex; flex-direction:column;">
        <div data-principle-image-card="{english.lower()}" style="height:372px; overflow:hidden; display:flex; flex:none;"><img src="{asset_id}" alt="{alt}" style="width:100%; height:100%; object-fit:cover; display:block;" data-ai-image="{asset_id}"></div>
        <div style="padding:30px 32px 34px; display:flex; flex-direction:column; gap:18px;">
          <div style="display:flex; align-items:baseline; gap:16px; white-space:nowrap;"><span style="font-size:26px; color:#3f6b4a;">{number}</span><span style="font-size:40px; font-weight:600;">{english}</span><span style="font-size:30px; color:#5b6b5e;">{korean}</span></div>
          <p style="margin:0; font-size:26px; line-height:1.62; font-weight:300; color:#4c5c50;">{body}</p>
        </div>
      </div>
'''
        )
    return f'''<section data-label="04 브랜드 원칙" data-screen-label="04" data-speaker-notes="Remove · Balance · Supply 3원칙. 이미지는 브랜드 원칙을 표현한 AI 생성 참고 이미지." style="background:#1f3325; color:#f8faf5; font-family:'IBM Plex Sans KR',sans-serif; padding:84px 96px; box-sizing:border-box; display:flex; flex-direction:column; gap:44px;">
    <div style="display:flex; justify-content:space-between; align-items:flex-end; gap:64px; flex:none;">
      <div style="display:flex; flex-direction:column; gap:18px;">
        <h2 style="margin:0; font-size:62px; font-weight:600; letter-spacing:-0.025em; line-height:1.18;">제로랩스가 간식을 만드는 세 가지 원칙</h2>
        <p style="margin:0; font-size:29px; line-height:1.65; font-weight:300; color:#cfdcd2; max-width:1100px;">불필요한 것은 덜어내고, 필요한 것은 목적에 맞게 조합하며, 파트너가 안정적으로 운영할 수 있는 구조를 만듭니다.</p>
      </div>
      <div style="display:flex; flex-direction:column; align-items:flex-end; gap:14px; max-width:650px; flex:none;">
        <span style="font-size:24px; letter-spacing:0.18em; color:#9dbaa5; white-space:nowrap;">02 — APPROACH</span>
        <p data-ai-image-disclosure="principle-reference-images" style="margin:0; font-size:19px; line-height:1.45; color:#cfdcd2; text-align:right;">{PRINCIPLE_DISCLOSURE}</p>
      </div>
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


def add_section_disclosure(template: str) -> str:
    if SECTION_DISCLOSURE in template:
        pattern = re.compile(
            r'<p data-ai-image-disclosure="production-reference-images" '
            r'style="[^"]*">'
            + re.escape(SECTION_DISCLOSURE)
            + r'</p>'
        )
        replacement = (
            '<p data-ai-image-disclosure="production-reference-images" '
            'style="margin:0; font-size:19px; line-height:1.45; '
            f'color:{SECTION_DISCLOSURE_COLOR}; flex:none;">'
            + SECTION_DISCLOSURE
            + "</p>"
        )
        template, count = pattern.subn(replacement, template)
        if count != 1:
            raise RuntimeError("Company profile AI image disclosure structure changed")
        return template
    section_match = re.search(
        r'<section\b[^>]*data-label="05 생산·원료".*?</section>', template, re.S
    )
    if not section_match:
        raise RuntimeError("Company profile production section is missing")
    section = section_match.group(0)
    ingredient_row = (
        '    <div style="display:flex; align-items:center; gap:24px; '
        'border-top:1px solid #ddd3c4; padding-top:20px; flex:none;">'
    )
    if section.count(ingredient_row) != 1:
        raise RuntimeError("Company profile ingredient row structure changed")
    note = (
        '    <p data-ai-image-disclosure="production-reference-images" '
        'style="margin:0; font-size:19px; line-height:1.45; '
        f'color:{SECTION_DISCLOSURE_COLOR}; flex:none;">'
        + SECTION_DISCLOSURE
        + "</p>\n"
    )
    section = section.replace(ingredient_row, note + ingredient_row, 1)
    return template[: section_match.start()] + section + template[section_match.end() :]


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
    template = add_section_disclosure(template)
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

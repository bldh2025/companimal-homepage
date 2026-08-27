#!/usr/bin/env python3
"""Embed the approved AI reference images in the standalone company profile."""

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
MAX_FACTORY_IMAGE_BYTES = 320_000

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


def add_card_disclosure(template: str, asset_id: str, alt: str) -> str:
    if f'src="{asset_id}"' not in template:
        raise RuntimeError(f"Company profile image reference is missing: {asset_id}")
    if f'src="{asset_id}" alt="{alt}"' in template and f'data-ai-image="{asset_id}"' in template:
        return template

    pattern = re.compile(
        r'(<div style="flex:1; min-height:56px; overflow:hidden; display:flex)'
        r'(;">)(<img\b[^>]*\bsrc="'
        + re.escape(asset_id)
        + r'"[^>]*>)(</div>)'
    )
    match = pattern.search(template)
    if not match:
        raise RuntimeError(f"Company profile image card structure changed: {asset_id}")
    image = re.sub(r'alt="[^"]*"', f'alt="{alt}"', match.group(3), count=1)
    image = image[:-1] + f' data-ai-image="{asset_id}">'
    badge = (
        f'<span data-ai-image-label="{asset_id}" '
        'style="position:absolute; right:10px; bottom:10px; background:#1f3325; '
        'color:#f4f8f0; padding:7px 10px; font-size:17px; line-height:1; '
        f'letter-spacing:0.02em;">{CARD_DISCLOSURE}</span>'
    )
    replacement = match.group(1) + "; position:relative" + match.group(2) + image + badge + match.group(4)
    return template[: match.start()] + replacement + template[match.end() :]


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

    for asset_id, spec in FACTORY_IMAGE_SPECS.items():
        asset_path = ROOT / spec["path"]
        data = asset_path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != spec["sha256"]:
            raise RuntimeError(f"Factory image SHA-256 mismatch: {asset_path}")
        if len(data) > MAX_FACTORY_IMAGE_BYTES:
            raise RuntimeError(f"Factory image exceeds size ceiling: {asset_path}")
        manifest[asset_id] = {
            "mime": "image/jpeg",
            "compressed": False,
            "data": base64.b64encode(data).decode("ascii"),
        }
        template = add_card_disclosure(template, asset_id, str(spec["alt"]))

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
    print(json.dumps({"status": "ok", "changed": changed, "images": len(FACTORY_IMAGE_SPECS)}))


if __name__ == "__main__":
    main()

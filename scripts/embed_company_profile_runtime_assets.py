#!/usr/bin/env python3
"""Embed the company-profile review data and enhancer for standalone downloads."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPANY_PROFILE = ROOT / "output" / "brochure" / "zerolabs-company-profile-ko-2026.html"
RUNTIME_ASSETS = (
    ("review-data", ROOT / "brochure-review-data.js", '../../brochure-review-data.js'),
    ("enhancer", ROOT / "company-contact-patch.js", '../../company-contact-patch.js'),
)


def inline_script(name: str, path: Path) -> str:
    payload = path.read_text(encoding="utf-8").rstrip()
    if re.search(r"</script|<!--|<script", payload, re.I):
        raise RuntimeError(f"Inline runtime asset contains an HTML script escape-state hazard: {path}")
    return f'<script data-company-profile-runtime="{name}">\n{payload}\n</script>'


def update_company_profile_runtime_assets(path: Path = COMPANY_PROFILE) -> bool:
    source = path.read_text(encoding="utf-8")
    updated = source
    for name, asset_path, external_src in RUNTIME_ASSETS:
        replacement = inline_script(name, asset_path)
        inline_pattern = re.compile(
            rf'<script data-company-profile-runtime="{re.escape(name)}">.*?</script>',
            re.S,
        )
        if inline_pattern.search(updated):
            updated, count = inline_pattern.subn(lambda _: replacement, updated)
        else:
            external_pattern = re.compile(
                rf'<script src="{re.escape(external_src)}"></script>'
            )
            updated, count = external_pattern.subn(lambda _: replacement, updated)
        if count != 1:
            raise RuntimeError(f"Company profile runtime asset hook is missing or duplicated: {name}")
    if updated == source:
        return False
    path.write_text(updated, encoding="utf-8")
    return True


def main() -> None:
    changed = update_company_profile_runtime_assets()
    print({"status": "ok", "changed": changed, "assets": len(RUNTIME_ASSETS)})


if __name__ == "__main__":
    main()

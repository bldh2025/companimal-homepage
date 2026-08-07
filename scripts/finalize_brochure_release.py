#!/usr/bin/env python3
"""Validate a complete v6/v3 brochure set, then atomically publish its manifest."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from brochure_content import LANGUAGES
from build_brochures import render_pdf
from validate_brochures import validate_pdf


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf"
MANIFEST = OUTPUT / "brochure-files.json"


def main() -> None:
    results: dict[str, dict[str, object]] = {}
    for code, language in LANGUAGES.items():
        company = OUTPUT / f"company-profile-{code}-2026-v6.pdf"
        product = OUTPUT / f"product-brochure-{code}-2026-v3.pdf"
        if not company.is_file() or not product.is_file() or company.is_symlink() or product.is_symlink():
            raise RuntimeError(f"Incomplete staged set for {code}")
        company_report = validate_pdf(company, code, language["locale"], 14, "company")
        product_report = validate_pdf(product, code, language["locale"], 16, "product")
        results[code] = {
            "label": language["label"],
            "label_ko": language["label_ko"],
            "locale": language["locale"],
            "company": {"path": str(company.relative_to(ROOT)), "bytes": company.stat().st_size, "pages": company_report["pages"]},
            "product": {"path": str(product.relative_to(ROOT)), "bytes": product.stat().st_size, "pages": product_report["pages"]},
        }
    staged = OUTPUT / "brochure-files.json.new"
    staged.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(staged, MANIFEST)
    preview = ROOT / "tmp" / "pdfs" / "rendered" / "company-profile-ko-2026-v6-contact-sheet.png"
    if preview.is_file():
        shutil.copy2(preview, OUTPUT / "company-profile-preview-ko.png")
    print(json.dumps({"status": "ok", "languages": len(results), "pdfs": len(results) * 2}, ensure_ascii=False))


if __name__ == "__main__":
    main()

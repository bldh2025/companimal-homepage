#!/usr/bin/env python3
"""Build and validate the latest company/product brochures, then publish."""

from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import subprocess

from brochure_content import LANGUAGES
from build_brochures import COMPANY_HTML_PAGE_COUNT, PRODUCT_PAGE_COUNT
from embed_company_profile_factory_images import update_company_profile_bundle
from embed_company_profile_runtime_assets import update_company_profile_runtime_assets
from validate_brochures import (
    validate_company_profile_pdf,
    validate_featured_html,
    validate_pdf,
    validate_product_html,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf"
MANIFEST = OUTPUT / "brochure-files.json"


def main() -> None:
    update_company_profile_bundle()
    update_company_profile_runtime_assets()
    subprocess.run(
        ["node", str(ROOT / "scripts" / "build_company_profile_pdf.mjs")],
        cwd=ROOT,
        check=True,
    )
    results: dict[str, dict[str, object]] = {}
    for code, language in LANGUAGES.items():
        product = OUTPUT / f"product-brochure-{code}-2026-v3.pdf"
        if not product.is_file() or product.is_symlink():
            raise RuntimeError(f"Incomplete staged set for {code}")
        product_report = validate_pdf(product, code, language["locale"], PRODUCT_PAGE_COUNT, "product")
        results[code] = {
            "label": language["label"],
            "label_ko": language["label_ko"],
            "locale": language["locale"],
            "product": {"path": str(product.relative_to(ROOT)), "bytes": product.stat().st_size, "pages": product_report["pages"]},
        }
    featured = ROOT / "output" / "brochure" / "zerolabs-company-profile-ko-2026.html"
    if not featured.is_file() or featured.is_symlink():
        raise RuntimeError(f"Missing featured HTML brochure: {featured}")
    results["ko"]["companyHtml"] = {
            "path": str(featured.relative_to(ROOT)),
            "bytes": featured.stat().st_size,
            "pages": COMPANY_HTML_PAGE_COUNT,
            "format": "html",
            "standalone": True,
            "sha256": hashlib.sha256(featured.read_bytes()).hexdigest(),
    }
    validate_featured_html(results["ko"]["companyHtml"])
    company = OUTPUT / "zerolabs-company-profile-ko-2026.pdf"
    if not company.is_file() or company.is_symlink():
        raise RuntimeError(f"Missing company PDF: {company}")
    company_report = validate_company_profile_pdf(company)
    results["ko"]["company"] = {
        "path": str(company.relative_to(ROOT)),
        "bytes": company.stat().st_size,
        "pages": company_report["pages"],
        "format": "pdf",
        "sha256": hashlib.sha256(company.read_bytes()).hexdigest(),
        "sourceSha256": results["ko"]["companyHtml"]["sha256"],
    }
    product_featured = ROOT / "output" / "brochure" / "zerolabs-product-profile-ko-2026-v2.html"
    if not product_featured.is_file() or product_featured.is_symlink():
        raise RuntimeError(f"Missing featured product HTML brochure: {product_featured}")
    results["ko"]["productHtml"] = {
        "path": str(product_featured.relative_to(ROOT)),
        "bytes": product_featured.stat().st_size,
        "pages": 16,
        "format": "html",
        "standalone": False,
        "sha256": hashlib.sha256(product_featured.read_bytes()).hexdigest(),
    }
    validate_product_html(results["ko"]["productHtml"])
    staged = OUTPUT / "brochure-files.json.new"
    staged.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(staged, MANIFEST)
    print(json.dumps({"status": "ok", "languages": len(results), "pdfs": len(results) + 1}, ensure_ascii=False))


if __name__ == "__main__":
    main()

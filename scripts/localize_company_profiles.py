#!/usr/bin/env python3
"""Generate standalone translations of the current 13-slide Korean company deck.

Run before build_company_profile_pdf.mjs <language>. Dictionaries match complete
text nodes; unknown Korean copy fails export so source changes cannot go unnoticed.
"""
from __future__ import annotations
import base64
import io
import json
from pathlib import Path
from fontTools import subset
from fontTools.ttLib import TTFont
from brochure_content import LANGUAGES

ROOT = Path(__file__).resolve().parents[1]
LOCALES = ROOT / 'scripts/company_locales'
LABEL_IDS = [0, 10, 11, 12, 13, 14, 195, 15, 16, 17, 18, 19, 20]


def content(code):
    source = json.loads((LOCALES / 'ko.json').read_text())
    values = json.loads((LOCALES / f'{code}.json').read_text())
    if len(source) != len(values) or not all(isinstance(v, str) and v for v in values):
        raise ValueError(f'Incomplete company translation: {code}')
    return {text: values[int(key)] for key, text in source.items()}, values


def font_css(code, characters):
    fonts = {
        'en': ('/System/Library/Fonts/Supplemental/Arial.ttf', None),
        'zh-hans': ('/System/Library/Fonts/Hiragino Sans GB.ttc', 0),
        'zh-hant': ('/System/Library/Fonts/Hiragino Sans GB.ttc', 0),
        'ja': ('/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc', 0),
        'th': (str(ROOT / 'zerolabs_homepage_assets/fonts/notosansthai.ttf'), None),
        'ar': (str(ROOT / 'zerolabs_homepage_assets/fonts/notosansarabic.ttf'), None),
    }
    filename, index = fonts[code]
    font = TTFont(filename, **({'fontNumber': index} if index is not None else {}))
    opts = subset.Options()
    opts.flavor = 'woff'
    opts.recalc_timestamp = False
    sub = subset.Subsetter(options=opts)
    # Thai shaping decomposes Sara Am into Nikhahit + Sara Aa. Retain the
    # whole small block, including marks absent from the input code points.
    if code == 'th':
        characters += ''.join(chr(cp) for cp in range(0x0E00, 0x0E80))
    sub.populate(text=characters)
    sub.subset(font)
    font.flavor = 'woff'
    out = io.BytesIO()
    font.save(out)
    data = base64.b64encode(out.getvalue()).decode()
    return "@font-face{font-family:CompanyLocale;src:url(data:font/woff;base64," + data + ") format('woff');font-weight:400;font-display:block;}"


def build(code):
    mapping, values = content(code)
    labels = [f'{i+1:02d} {values[key]}' for i, key in enumerate(LABEL_IDS)]
    config = dict(code=code, locale=LANGUAGES[code]['locale'], mapping=mapping,
                  labels=labels, reviewUnit=values[198], title=f'{values[11]} | ZERO LABS 2026')
    # Include original ASCII labels/numbers and the Korean wholesale domain.
    css = font_css(code, ''.join(values) + ''.join(chr(i) for i in range(32,127)) + '·©✓')
    css += '''
section, section * { font-family:CompanyLocale,Arial,sans-serif !important; }
section * { min-width:0; }
section h1, section h2, section h3 { overflow-wrap:normal; }
section [data-locale-text] { letter-spacing:0 !important; }
'''
    script = (ROOT / 'scripts/company_profile_localize.js').read_text()
    script = script.replace('__COMPANY_LOCALE_CONFIG__', json.dumps(config, ensure_ascii=False))
    script = script.replace('__COMPANY_LOCALE_CSS__', json.dumps(css, ensure_ascii=False))
    source = (ROOT / 'output/brochure/zerolabs-company-profile-ko-2026.html').read_text()
    hook = '    document.documentElement.replaceWith(doc.documentElement);'
    if source.count(hook) != 1:
        raise ValueError('Company bundle localization hook changed')
    source = source.replace(hook, '    window.localizeCompanyProfile(doc);\n' + hook)
    source = source.replace('</head>', '<script data-company-locale="' + code + '">\n' + script + '\n</script>\n</head>', 1)
    source = source.replace('<html>', f'<html lang="{LANGUAGES[code]["locale"]}" dir="{"rtl" if code == "ar" else "ltr"}">', 1)
    target = ROOT / f'output/brochure/zerolabs-company-profile-{code}-2026.html'
    target.write_text(source)
    return target


if __name__ == '__main__':
    import sys
    for code in (sys.argv[1:] or [c for c in LANGUAGES if c != 'ko']):
        print(build(code).relative_to(ROOT))

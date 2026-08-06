#!/usr/bin/env python3
"""Build localized, searchable ZERO LABS PDF brochures.

Outputs are generated from one content source so the website manifest and all
language variants cannot drift independently.
"""

from __future__ import annotations

import argparse
import html
import io
import json
import shutil
from pathlib import Path

import fitz
import qrcode
from PIL import Image, ImageChops, ImageDraw, ImageOps
from fontTools.ttLib import TTCollection
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, TextStringObject

from brochure_content import COMPANY_CONTENT, LANGUAGES, PRODUCT_CONTENT


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "zerolabs_homepage_assets"
OUTPUT = ROOT / "output" / "pdf"
TMP = ROOT / "tmp" / "pdfs"
FONT_DIR = TMP / "fonts"
RENDER_DIR = TMP / "rendered"
SOURCE_PDF = ROOT / ".orca" / "drops" / "브로슈어_중국어버전_2026.pdf"
SOURCE_RENDER_DIR = TMP / "source-render"
SOURCE_SANITIZED_DIR = TMP / "source-sanitized"

PAGE = fitz.Rect(0, 0, 595, 842)
SOURCE_PAGE = fitz.Rect(0, 0, 1066, 1492)
FOREST = (22 / 255, 36 / 255, 26 / 255)
GREEN = (31 / 255, 51 / 255, 37 / 255)
MID_GREEN = (44 / 255, 70 / 255, 50 / 255)
CREAM = (245 / 255, 241 / 255, 232 / 255)
CREAM_2 = (236 / 255, 230 / 255, 214 / 255)
GOLD = (216 / 255, 179 / 255, 106 / 255)
WHITE = (1, 1, 1)

CONTACT_VALUES = [
    "https://companimal.kr",
    "https://zerolabs.co.kr",
    "https://제로랩스.com",
    "https://pf.kakao.com/_xnyDcs",
    "bldh2025@naver.com",
    "Unit 215-26, 30 Namdong-seoro 236beon-gil, Namdong-gu, Incheon, Republic of Korea",
]

PRODUCT_CONTACT_VALUES = [
    "https://companimal.kr",
    "https://pf.kakao.com/_xnyDcs",
    "bldh2025@naver.com",
    "Unit 215-26, 30 Namdong-seoro 236beon-gil, Namdong-gu, Incheon, Republic of Korea",
]

COMPANY_DETAIL = {
    "ko": {
        "identity": ("COMPANY IDENTITY", "브랜드와 유통을 연결하는 운영사", "반려동행은 ZERO LABS의 제품 기획·정보 정리·채널 운영을 하나의 흐름으로 연결합니다. 보호자에게는 이해하기 쉬운 선택 기준을, 파트너에게는 검토와 판매에 필요한 기본 정보를 제공합니다."),
        "identity_points": [("브랜드 운영", "ZERO LABS의 방향과 제품 포트폴리오를 일관되게 관리합니다."), ("제품 정보", "제품군과 포장 단위를 명확히 정리해 거래 검토를 돕습니다."), ("채널 연결", "공식몰·오픈마켓·도매몰을 목적에 맞게 운영합니다.")],
        "model": ("BUSINESS MODEL", "기획부터 판매 채널까지 이어지는 구조", "제품을 만들고 끝나는 것이 아니라, 정보와 공급, 고객 접점이 계속 이어지도록 운영합니다."),
        "model_steps": [("01 · 기획", "고객 니즈와 급여 상황에 맞춰 제품군과 포장 규격을 구성합니다."), ("02 · 생산·공급", "국내 제조 파트너와 협력하고 반복 주문을 고려해 공급을 운영합니다."), ("03 · 판매·피드백", "B2C와 B2B 채널에서 확인한 반응을 제품 정보와 운영에 반영합니다.")],
        "categories": ("PORTFOLIO DETAIL", "용도와 형태로 이해하는 제품 구성", "져키·덴탈·베이크드·식물성·시리얼 타입을 대용량과 소용량으로 구성해 고객과 채널별 제안 폭을 넓혔습니다."),
        "channels": ("CHANNELS", "보호자와 파트너를 연결하는 네 가지 채널", "공식몰과 오픈마켓은 소비자 구매 접점을, 도매몰은 펫샵과 온라인 셀러의 거래 접점을 담당합니다."),
        "channel_items": [("ZERO LABS 공식몰", "브랜드와 제품을 직접 확인하는 B2C 채널"), ("쿠팡", "주요 제품을 구매할 수 있는 오픈마켓 채널"), ("B2B 도매몰", "펫샵·온라인 셀러를 위한 거래 채널"), ("네이버 스마트스토어", "네이버 기반 소비자 판매 채널")],
        "consultation": "MOQ, 공급가, 마진, 리드타임과 판매 가능 품목은 거래 형태에 따라 개별 상담합니다.",
    },
    "en": {
        "identity": ("COMPANY IDENTITY", "An operator connecting brand and distribution", "Companimal connects ZERO LABS product planning, information management, and channel operations in one workflow. Consumers receive clearer choices, while partners receive the core information needed to review and sell the range."),
        "identity_points": [("Brand operation", "Maintain a consistent direction and portfolio for ZERO LABS."), ("Product information", "Organize categories and pack sizes for efficient trade review."), ("Channel connection", "Operate official, marketplace, and wholesale touchpoints by purpose.")],
        "model": ("BUSINESS MODEL", "A structure from planning to sales channels", "Our work continues beyond production by linking product information, supply operations, and customer touchpoints."),
        "model_steps": [("01 · Plan", "Shape product categories and pack formats around needs and feeding occasions."), ("02 · Make & supply", "Work with Korean manufacturing partners and operate for repeat orders."), ("03 · Sell & learn", "Use B2C and B2B feedback to improve information and operations.")],
        "categories": ("PORTFOLIO DETAIL", "A range organized by purpose and format", "Jerky, dental, baked, plant-based, and cereal formats span value and smaller packs for different customers and channels."),
        "channels": ("CHANNELS", "Four channels connecting consumers and partners", "The official store and marketplaces serve consumer purchasing, while the wholesale store supports pet shops and online sellers."),
        "channel_items": [("ZERO LABS official store", "Direct B2C brand and product channel"), ("Coupang", "Marketplace channel for core products"), ("B2B wholesale store", "Trade channel for pet shops and online sellers"), ("Naver Smart Store", "Consumer sales channel on Naver")],
        "consultation": "MOQ, supply price, margin, lead time, and available items are confirmed through individual consultation.",
    },
    "zh-hans": {
        "identity": ("企业定位", "连接品牌与流通的运营公司", "Companimal 将 ZERO LABS 的产品企划、信息整理与渠道运营连接为统一流程，为消费者提供清晰的选择依据，也为合作伙伴提供审核与销售所需的基础信息。"),
        "identity_points": [("品牌运营", "统一管理 ZERO LABS 的品牌方向与产品组合。"), ("产品信息", "清晰整理产品类别与包装规格，便于交易审核。"), ("渠道连接", "按用途运营官网、平台与批发渠道。")],
        "model": ("业务模式", "从企划延伸至销售渠道的运营结构", "产品生产并非终点，我们持续连接产品信息、供应运营与客户接触点。"),
        "model_steps": [("01 · 企划", "根据客户需求与喂食场景规划产品类别和包装规格。"), ("02 · 生产与供应", "与韩国制造伙伴合作，并以持续订货为目标管理供应。"), ("03 · 销售与反馈", "将 B2C 与 B2B 渠道反馈用于改善信息与运营。")],
        "categories": ("产品组合详情", "按用途与形态理解产品", "肉条、洁齿、烘焙、植物性与谷物型产品提供大包装和小包装，适配不同客户与渠道。"),
        "channels": ("销售渠道", "连接消费者与合作伙伴的四类渠道", "官方商城与平台服务消费者购买，批发商城面向宠物店和线上卖家。"),
        "channel_items": [("ZERO LABS 官方商城", "品牌与产品的直营 B2C 渠道"), ("Coupang", "核心产品的平台销售渠道"), ("B2B 批发商城", "面向宠物店与线上卖家的交易渠道"), ("Naver Smart Store", "基于 Naver 的消费者销售渠道")],
        "consultation": "起订量、供货价、利润率、交期与可售品项需根据交易方式单独协商。",
    },
    "zh-hant": {
        "identity": ("企業定位", "連接品牌與流通的營運公司", "Companimal 將 ZERO LABS 的產品企劃、資訊整理與通路營運連接為統一流程，為消費者提供清晰的選擇依據，也為合作夥伴提供審核與銷售所需的基本資訊。"),
        "identity_points": [("品牌營運", "統一管理 ZERO LABS 的品牌方向與產品組合。"), ("產品資訊", "清楚整理產品類別與包裝規格，便於交易審核。"), ("通路連接", "依用途營運官網、平台與批發通路。")],
        "model": ("業務模式", "從企劃延伸至銷售通路的營運結構", "產品生產並非終點，我們持續連接產品資訊、供應營運與客戶接觸點。"),
        "model_steps": [("01 · 企劃", "依客戶需求與餵食情境規劃產品類別和包裝規格。"), ("02 · 生產與供應", "與韓國製造夥伴合作，並以持續訂貨為目標管理供應。"), ("03 · 銷售與回饋", "將 B2C 與 B2B 通路回饋用於改善資訊與營運。")],
        "categories": ("產品組合詳情", "依用途與形態理解產品", "肉條、潔牙、烘焙、植物性與穀物型產品提供大包裝和小包裝，適合不同客戶與通路。"),
        "channels": ("銷售通路", "連接消費者與合作夥伴的四類通路", "官方商城與平台服務消費者購買，批發商城則面向寵物店與線上賣家。"),
        "channel_items": [("ZERO LABS 官方商城", "品牌與產品的直營 B2C 通路"), ("Coupang", "核心產品的平台銷售通路"), ("B2B 批發商城", "面向寵物店與線上賣家的交易通路"), ("Naver Smart Store", "基於 Naver 的消費者銷售通路")],
        "consultation": "最低訂購量、供貨價、利潤率、交期與可售品項將依交易方式個別洽談。",
    },
    "ja": {
        "identity": ("COMPANY IDENTITY", "ブランドと流通をつなぐ運営会社", "Companimalは、ZERO LABSの商品企画・情報整理・チャネル運営を一つの流れにつなぎます。消費者には分かりやすい選択基準を、パートナーには検討と販売に必要な基本情報を提供します。"),
        "identity_points": [("ブランド運営", "ZERO LABSの方向性とポートフォリオを一貫して管理します。"), ("商品情報", "商品カテゴリーと容量を明確に整理し、取引検討を支援します。"), ("チャネル連携", "公式・モール・卸売の接点を目的別に運営します。")],
        "model": ("BUSINESS MODEL", "企画から販売チャネルまで続く仕組み", "製造で終わらず、商品情報・供給運営・顧客接点が継続してつながるよう運営します。"),
        "model_steps": [("01 · 企画", "顧客ニーズと給与シーンに合わせて商品群と容量を構成します。"), ("02 · 生産・供給", "韓国の製造パートナーと協力し、継続発注を考慮して供給します。"), ("03 · 販売・改善", "B2CとB2Bの反応を商品情報と運営に反映します。")],
        "categories": ("PORTFOLIO DETAIL", "用途と形状で理解する商品構成", "ジャーキー、デンタル、ベイクド、植物性、シリアルタイプを大容量と小容量で展開し、顧客とチャネル別の提案幅を広げます。"),
        "channels": ("CHANNELS", "消費者とパートナーを結ぶ4つのチャネル", "公式ストアとモールは消費者の購入接点を、卸売ストアはペットショップとオンラインセラーの取引接点を担います。"),
        "channel_items": [("ZERO LABS公式ストア", "ブランドと商品を直接確認するB2Cチャネル"), ("Coupang", "主要商品を購入できるモールチャネル"), ("B2B卸売ストア", "ペットショップ・オンラインセラー向け取引チャネル"), ("Naver Smart Store", "Naver上の消費者販売チャネル")],
        "consultation": "MOQ、供給価格、マージン、リードタイム、取扱可能商品は取引形態に応じて個別にご案内します。",
    },
    "th": {
        "identity": ("อัตลักษณ์บริษัท", "ผู้ดำเนินงานที่เชื่อมแบรนด์และการจัดจำหน่าย", "Companimal เชื่อมการวางแผนสินค้า การจัดการข้อมูล และการดำเนินงานช่องทางของ ZERO LABS เป็นกระบวนการเดียว ผู้บริโภคจึงเลือกได้ง่ายขึ้น และพันธมิตรได้รับข้อมูลพื้นฐานสำหรับพิจารณาและจำหน่ายสินค้า"),
        "identity_points": [("การบริหารแบรนด์", "ดูแลทิศทางและพอร์ตสินค้า ZERO LABS ให้สอดคล้องกัน"), ("ข้อมูลสินค้า", "จัดหมวดหมู่และขนาดบรรจุให้ชัดเจนเพื่อการพิจารณาธุรกิจ"), ("การเชื่อมช่องทาง", "บริหารร้านทางการ มาร์เก็ตเพลส และช่องทางค้าส่งตามวัตถุประสงค์")],
        "model": ("รูปแบบธุรกิจ", "โครงสร้างตั้งแต่การวางแผนถึงช่องทางขาย", "งานของเราไม่จบที่การผลิต แต่เชื่อมข้อมูลสินค้า การจัดหาสินค้า และจุดสัมผัสลูกค้าอย่างต่อเนื่อง"),
        "model_steps": [("01 · วางแผน", "กำหนดหมวดสินค้าและขนาดบรรจุตามความต้องการและโอกาสการให้อาหาร"), ("02 · ผลิตและจัดหา", "ร่วมงานกับผู้ผลิตในเกาหลีและบริหารการจัดหาสำหรับคำสั่งซื้อซ้ำ"), ("03 · ขายและเรียนรู้", "นำผลตอบรับจาก B2C และ B2B มาปรับข้อมูลและการดำเนินงาน")],
        "categories": ("รายละเอียดพอร์ตสินค้า", "เข้าใจสินค้าได้จากวัตถุประสงค์และรูปแบบ", "สินค้าประเภทเจอร์กี เดนทัล อบ พืช และซีเรียล มีทั้งขนาดคุ้มค่าและขนาดเล็กสำหรับลูกค้าและช่องทางที่ต่างกัน"),
        "channels": ("ช่องทาง", "สี่ช่องทางเชื่อมผู้บริโภคและพันธมิตร", "ร้านทางการและมาร์เก็ตเพลสรองรับการซื้อของผู้บริโภค ส่วนร้านค้าส่งรองรับร้านเพ็ทช็อปและผู้ขายออนไลน์"),
        "channel_items": [("ร้าน ZERO LABS ทางการ", "ช่องทาง B2C โดยตรงของแบรนด์และสินค้า"), ("Coupang", "ช่องทางมาร์เก็ตเพลสสำหรับสินค้าหลัก"), ("ร้านค้าส่ง B2B", "ช่องทางธุรกิจสำหรับร้านเพ็ทช็อปและผู้ขายออนไลน์"), ("Naver Smart Store", "ช่องทางขายผู้บริโภคบน Naver")],
        "consultation": "MOQ ราคาส่ง มาร์จิน ระยะเวลาส่งมอบ และรายการสินค้าที่จำหน่ายได้ จะแจ้งเป็นรายกรณีตามรูปแบบการค้า",
    },
    "ar": {
        "identity": ("هوية الشركة", "مشغل يربط العلامة بالتوزيع", "تربط Companimal تخطيط منتجات ZERO LABS وإدارة المعلومات وتشغيل القنوات ضمن مسار واحد. يحصل المستهلك على خيارات أوضح، ويحصل الشريك على المعلومات الأساسية اللازمة للمراجعة والبيع."),
        "identity_points": [("تشغيل العلامة", "إدارة اتجاه ZERO LABS ومحفظتها بصورة متسقة."), ("معلومات المنتج", "تنظيم الفئات وأحجام العبوات لتسهيل مراجعة التجارة."), ("ربط القنوات", "تشغيل المتجر الرسمي والمنصات وقناة الجملة بحسب الغرض.")],
        "model": ("نموذج الأعمال", "هيكل يمتد من التخطيط إلى قنوات البيع", "لا ينتهي عملنا عند الإنتاج؛ بل نربط معلومات المنتج والتوريد ونقاط التواصل مع العملاء باستمرار."),
        "model_steps": [("01 · التخطيط", "تشكيل الفئات وأحجام العبوات وفق الاحتياجات ومناسبات التقديم."), ("02 · الإنتاج والتوريد", "التعاون مع شركاء تصنيع في كوريا وإدارة التوريد للطلبات المتكررة."), ("03 · البيع والتعلم", "استخدام ملاحظات قنوات B2C وB2B لتحسين المعلومات والتشغيل.")],
        "categories": ("تفاصيل المحفظة", "مجموعة منظمة حسب الغرض والشكل", "تشمل المجموعة الجيركي والعناية بالأسنان والمخبوز والنباتي والحبوب، بأحجام كبيرة وصغيرة تناسب العملاء والقنوات المختلفة."),
        "channels": ("القنوات", "أربع قنوات تربط المستهلكين والشركاء", "يخدم المتجر الرسمي والمنصات مشتريات المستهلكين، بينما يدعم متجر الجملة متاجر الحيوانات والبائعين عبر الإنترنت."),
        "channel_items": [("متجر ZERO LABS الرسمي", "قناة B2C مباشرة للعلامة والمنتجات"), ("Coupang", "قناة سوق للمنتجات الأساسية"), ("متجر الجملة B2B", "قناة تجارة لمتاجر الحيوانات والبائعين عبر الإنترنت"), ("Naver Smart Store", "قناة بيع للمستهلك عبر Naver")],
        "consultation": "يتم تأكيد الحد الأدنى للطلب وسعر التوريد والهامش ومدة التسليم والأصناف المتاحة عبر استشارة فردية.",
    },
}

COMPANY_PAGE_LABELS = {
    "ko": {"pack_note": "제품별 포장 단위입니다. 상세 사양은 공식 문의 채널에서 확인합니다.", "history_note": "2025년 이전은 ZERO LABS 브랜드 연혁이며, 2025년부터 주식회사 반려동행의 운영 이력을 구분해 표시했습니다.", "review": "검토", "consult": "상담"},
    "en": {"pack_note": "Pack sizes are listed by product line. Confirm detailed specifications through the official inquiry channels.", "history_note": "Milestones before 2025 refer to the ZERO LABS brand; Companimal operations are identified from 2025 onward.", "review": "Review", "consult": "Consult"},
    "zh-hans": {"pack_note": "以上为各产品线包装规格，详细参数请通过官方渠道确认。", "history_note": "2025年前为 ZERO LABS 品牌历程，2025年起另行标示 Companimal 的运营历程。", "review": "审核", "consult": "洽谈"},
    "zh-hant": {"pack_note": "以上為各產品線包裝規格，詳細參數請透過官方管道確認。", "history_note": "2025年前為 ZERO LABS 品牌歷程，2025年起另行標示 Companimal 的營運歷程。", "review": "審核", "consult": "洽談"},
    "ja": {"pack_note": "商品ライン別の容量です。詳細仕様は公式窓口でご確認ください。", "history_note": "2025年以前はZERO LABSのブランド沿革、2025年以降はCompanimalの運営履歴として区分しています。", "review": "検討", "consult": "相談"},
    "th": {"pack_note": "ระบุขนาดบรรจุตามไลน์สินค้า โปรดยืนยันรายละเอียดผ่านช่องทางติดต่อทางการ", "history_note": "ก่อนปี 2025 เป็นประวัติของแบรนด์ ZERO LABS และตั้งแต่ปี 2025 แยกเป็นการดำเนินงานของ Companimal", "review": "ตรวจสอบ", "consult": "ปรึกษา"},
    "ar": {"pack_note": "تُعرض أحجام العبوات حسب خط المنتج. تُؤكد المواصفات عبر قنوات التواصل الرسمية.", "history_note": "تمثل المراحل قبل 2025 تاريخ علامة ZERO LABS، وتُعرض عمليات Companimal ابتداء من 2025 بصورة منفصلة.", "review": "مراجعة", "consult": "استشارة"},
}

FONT_FILES = {
    "en": (Path("/System/Library/Fonts/Supplemental/Arial.ttf"), Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf")),
    "ko": (FONT_DIR / "ko-regular.ttf", FONT_DIR / "ko-bold.ttf"),
    "cjk": (FONT_DIR / "cjk-regular.ttf", FONT_DIR / "cjk-bold.ttf"),
    "th": (FONT_DIR / "th-regular.ttf", FONT_DIR / "th-bold.ttf"),
    "ar": (FONT_DIR / "ar-regular.ttf", FONT_DIR / "ar-bold.ttf"),
}

PRODUCT_IMAGES = {
    "meat": ASSETS / "products" / "gogi.webp",
    "nutrition": ASSETS / "products" / "yeongyang.webp",
    "berry": ASSETS / "products" / "berry.webp",
    "baked": ASSETS / "products" / "gupbbang.webp",
    "fresh": ASSETS / "products" / "fresh.webp",
    "mungs": ASSETS / "products" / "mungs.webp",
    "dental": ASSETS / "products" / "chika.webp",
    "meatless": ASSETS / "products" / "meatless.webp",
}

FONT_SOURCES = {
    "ko": (Path("/System/Library/Fonts/AppleSDGothicNeo.ttc"), (0, 6)),
    "cjk": (Path("/System/Library/Fonts/Hiragino Sans GB.ttc"), (0, 2)),
    "th": (Path("/System/Library/Fonts/Supplemental/Thonburi.ttc"), (0, 1)),
    "ar": (Path("/System/Library/Fonts/GeezaPro.ttc"), (0, 1)),
}


def prepare_font_files() -> None:
    """Extract the required macOS TTC faces into the ignored build cache."""
    FONT_DIR.mkdir(parents=True, exist_ok=True)
    for key, (collection_path, indices) in FONT_SOURCES.items():
        regular, bold = FONT_FILES[key]
        if not collection_path.exists():
            raise FileNotFoundError(f"Required system font is unavailable: {collection_path}")
        source_regular = FONT_DIR / f"{key}-source-regular.ttf"
        source_bold = FONT_DIR / f"{key}-source-bold.ttf"
        if not source_regular.exists() or not source_bold.exists():
            collection = TTCollection(str(collection_path))
            collection.fonts[indices[0]].save(source_regular)
            collection.fonts[indices[1]].save(source_bold)
        for source_font, target in ((source_regular, regular), (source_bold, bold)):
            if not target.exists() or target.stat().st_size < source_font.stat().st_size * 0.9:
                shutil.copy2(source_font, target)


def ensure_inputs() -> None:
    missing = []
    for regular, bold in FONT_FILES.values():
        if not regular.exists():
            missing.append(str(regular))
        if not bold.exists():
            missing.append(str(bold))
    for path in list(PRODUCT_IMAGES.values()) + [
        SOURCE_PDF,
        ASSETS / "hero-dog-companion.webp",
        ASSETS / "hero-dog-treats.webp",
        ASSETS / "team_walk.webp",
        ASSETS / "make_oem.webp",
        ASSETS / "make_ingredient.webp",
        ASSETS / "make_supply.webp",
        ASSETS / "approach_remove.webp",
        ASSETS / "approach_balance.webp",
        ASSETS / "lockup_zerolabs.png",
        ASSETS / "lockup_companimal.png",
    ]:
        if not path.exists():
            missing.append(str(path))
    if missing:
        raise FileNotFoundError("Missing brochure inputs:\n" + "\n".join(missing))


def rgb_css(color: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{round(v * 255):02x}" for v in color)


def css_for(lang: str) -> tuple[str, fitz.Archive]:
    font_key = LANGUAGES[lang]["font"]
    regular, bold = FONT_FILES[font_key]
    archive = fitz.Archive(str(regular.parent))
    direction = LANGUAGES[lang]["dir"]
    align = "right" if direction == "rtl" else "left"
    css = f"""
    @font-face {{ font-family: Brochure; src: url('{regular.name}'); font-weight: 400; }}
    @font-face {{ font-family: Brochure; src: url('{bold.name}'); font-weight: 700; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Brochure; direction: {direction}; text-align: {align}; color: #16241a; }}
    p, h1, h2, h3, h4 {{ margin: 0; padding: 0; }}
    .kicker {{ color: #a57d30; font-size: 10pt; font-weight: 700; letter-spacing: 1.4pt; }}
    .title {{ font-size: 28pt; line-height: 1.18; font-weight: 700; }}
    .subtitle {{ font-size: 12pt; line-height: 1.55; color: #506056; }}
    .white {{ color: #ffffff; }}
    .soft {{ color: #dce2dc; }}
    .gold {{ color: #d8b36a; }}
    .body {{ font-size: 11.5pt; line-height: 1.65; }}
    .small {{ font-size: 8.5pt; line-height: 1.5; }}
    .label {{ font-size: 9pt; font-weight: 700; color: #a57d30; }}
    .value {{ font-size: 12pt; line-height: 1.45; font-weight: 700; }}
    .card-title {{ font-size: 16pt; font-weight: 700; line-height: 1.25; }}
    .card-body {{ font-size: 9.5pt; color: #506056; line-height: 1.55; }}
    .card-body.soft {{ color: #dce2dc; }}
    .metric {{ font-size: 25pt; font-weight: 700; color: #d8b36a; }}
    .metric-label {{ font-size: 8.5pt; line-height: 1.35; color: #e6ece6; }}
    ul {{ margin: 5pt 0 0 0; padding-inline-start: 15pt; }}
    li {{ font-size: 9.5pt; line-height: 1.5; margin-bottom: 2pt; }}
    """
    return css, archive


def add_html(page: fitz.Page, rect: fitz.Rect, markup: str, lang: str, *, scale_low: float = 0.68) -> None:
    css, archive = css_for(lang)
    spare, scale = page.insert_htmlbox(rect, markup, css=css, archive=archive, scale_low=scale_low)
    if spare < -0.01:
        raise RuntimeError(f"Text overflow on page {page.number + 1}: spare={spare}, scale={scale}")


def add_image_cover(page: fitz.Page, rect: fitz.Rect, path: Path, opacity: float | None = None) -> None:
    path = cover_image(path, rect)
    page.insert_image(rect, filename=str(path), keep_proportion=True)
    if opacity is not None:
        page.draw_rect(rect, color=None, fill=FOREST, fill_opacity=opacity, overlay=True)


def add_image_fit(page: fitz.Page, rect: fitz.Rect, path: Path, *, radius: float = 0) -> None:
    # PyMuPDF clipping is rectangular; the surrounding card provides the visual radius.
    path = compatible_image(path)
    page.insert_image(rect, filename=str(path), keep_proportion=True)
    if radius:
        page.draw_rect(rect, color=(0.84, 0.82, 0.76), width=0.5, radius=radius, overlay=True)


def add_logo(page: fitz.Page, kind: str, rect: fitz.Rect) -> None:
    path = ASSETS / ("lockup_zerolabs.png" if kind == "zero" else "lockup_companimal.png")
    page.insert_image(rect, filename=str(path), keep_proportion=True, overlay=True)


def compatible_image(path: Path) -> Path:
    """Return an optimized JPEG copy for formats unsupported by local MuPDF."""
    if path.suffix.lower() != ".webp":
        return path
    cache_dir = TMP / "image-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / f"{path.parent.name}-{path.stem}.jpg"
    if not target.exists() or target.stat().st_mtime < path.stat().st_mtime:
        Image.open(path).convert("RGB").save(target, quality=92, optimize=True, progressive=True)
    return target


def cover_image(path: Path, rect: fitz.Rect) -> Path:
    """Crop uniformly to a target rectangle; never stretch an input image."""
    cache_dir = TMP / "image-cache" / "cover"
    cache_dir.mkdir(parents=True, exist_ok=True)
    width = max(1, round(rect.width * 2))
    height = max(1, round(rect.height * 2))
    target = cache_dir / f"{path.parent.name}-{path.stem}-{width}x{height}.jpg"
    if not target.exists() or target.stat().st_mtime < path.stat().st_mtime:
        with Image.open(path) as source:
            cropped = ImageOps.fit(source.convert("RGB"), (width, height), method=Image.Resampling.LANCZOS)
            cropped.save(target, quality=92, optimize=True, progressive=True)
    return target


def new_page(doc: fitz.Document, fill: tuple[float, float, float] = CREAM) -> fitz.Page:
    page = doc.new_page(width=PAGE.width, height=PAGE.height)
    page.draw_rect(PAGE, color=None, fill=fill)
    return page


def new_source_page(doc: fitz.Document) -> fitz.Page:
    return doc.new_page(width=SOURCE_PAGE.width, height=SOURCE_PAGE.height)


def add_footer(page: fitz.Page, page_no: int, total: int, lang: str, *, light: bool = False) -> None:
    color = "#dce2dc" if light else "#657268"
    direction = LANGUAGES[lang]["dir"]
    left = "ZERO LABS · Companimal Co., Ltd."
    markup = f'<p class="small" style="color:{color}; direction:{direction}">{html.escape(left)}</p>'
    add_html(page, fitz.Rect(42, 810, 440, 830), markup, lang)
    add_html(page, fitz.Rect(500, 810, 553, 830), f'<p class="small" style="color:{color}; text-align:right">{page_no:02d} / {total:02d}</p>', lang)


def title_block(page: fitz.Page, lang: str, kicker: str, title: str, subtitle: str = "", *, y: float = 48, light: bool = False) -> None:
    classes = "title white" if light else "title"
    subtitle_class = "subtitle soft" if light else "subtitle"
    markup = f'<p class="kicker">{html.escape(kicker)}</p><p class="{classes}" style="margin-top:9pt">{html.escape(title)}</p>'
    if subtitle:
        markup += f'<p class="{subtitle_class}" style="margin-top:11pt">{html.escape(subtitle)}</p>'
    add_html(page, fitz.Rect(42, y, 553, y + 125), markup, lang)


def qr_png(url: str, name: str) -> Path:
    TMP.mkdir(parents=True, exist_ok=True)
    target = TMP / name
    img = qrcode.make(url)
    img.save(target)
    return target


def company_brochure(lang: str) -> fitz.Document:
    c = COMPANY_CONTENT[lang]
    detail = COMPANY_DETAIL[lang]
    labels = COMPANY_PAGE_LABELS[lang]
    doc = fitz.open()
    total = 14

    # 1. Cover
    p = new_page(doc, FOREST)
    add_image_cover(p, PAGE, ASSETS / "hero-dog-companion.webp", 0.53)
    p.draw_rect(fitz.Rect(0, 0, 16, 842), color=None, fill=GOLD)
    add_logo(p, "company", fitz.Rect(42, 46, 138, 138))
    add_html(p, fitz.Rect(42, 180, 540, 440), f'<p class="kicker gold">{html.escape(c["cover_badge"])}</p><p class="title white" style="font-size:35pt; margin-top:14pt">{html.escape(c["cover_title"]).replace(chr(10), "<br>")}</p><p class="subtitle soft" style="margin-top:18pt">{html.escape(c["cover_subtitle"])}</p>', lang)
    add_html(p, fitz.Rect(42, 740, 550, 790), '<p class="small white">COMPANION ANIMAL BUSINESS · INCHEON, KOREA</p>', lang)

    # 2. Overview
    p = new_page(doc)
    title_block(p, lang, c["overview_kicker"], c["overview_title"], c["overview_body"])
    p.draw_rect(fitz.Rect(42, 210, 553, 355), radius=0.08, color=None, fill=FOREST)
    metric_w = 119
    for i, (value, label) in enumerate(c["metrics"]):
        x = 54 + i * 124
        add_html(p, fitz.Rect(x, 235, x + metric_w, 328), f'<p class="metric">{html.escape(value)}</p><p class="metric-label" style="margin-top:5pt">{html.escape(label)}</p>', lang)
        if i < 3:
            p.draw_line(fitz.Point(x + metric_w, 238), fitz.Point(x + metric_w, 326), color=MID_GREEN, width=1)
    add_image_cover(p, fitz.Rect(42, 390, 280, 755), ASSETS / "team_walk.webp")
    p.draw_rect(fitz.Rect(302, 390, 553, 755), radius=0.05, color=None, fill=CREAM_2)
    fact_markup = "".join(f'<p class="value" style="margin-bottom:19pt">{html.escape(item)}</p>' for item in c["facts"])
    add_html(p, fitz.Rect(328, 426, 528, 726), fact_markup, lang)
    add_footer(p, 2, total, lang)

    # 3. Company identity
    p = new_page(doc, FOREST)
    kicker, title, body = detail["identity"]
    title_block(p, lang, kicker, title, body, light=True)
    add_image_cover(p, fitz.Rect(42, 205, 553, 430), ASSETS / "hero-dog-treats.webp")
    for i, (label, copy) in enumerate(detail["identity_points"]):
        x = 42 + i * 171
        p.draw_rect(fitz.Rect(x, 465, x + 154, 710), radius=0.06, color=None, fill=GREEN)
        add_html(p, fitz.Rect(x + 15, 493, x + 139, 685), f'<p class="kicker">0{i + 1}</p><p class="card-title white" style="font-size:13pt;margin-top:9pt">{html.escape(label)}</p><p class="card-body soft" style="font-size:8.8pt;margin-top:12pt">{html.escape(copy)}</p>', lang, scale_low=0.55)
    add_footer(p, 3, total, lang, light=True)

    # 4. Principles
    p = new_page(doc)
    title_block(p, lang, c["principles_kicker"], c["principles_title"])
    principle_images = [ASSETS / "approach_remove.webp", ASSETS / "approach_balance.webp", ASSETS / "hero-dog-treats.webp"]
    for i, ((label, body), image_path) in enumerate(zip(c["principles"], principle_images)):
        y = 155 + i * 204
        p.draw_rect(fitz.Rect(42, y, 553, y + 176), radius=0.08, color=None, fill=WHITE)
        add_image_cover(p, fitz.Rect(42, y, 245, y + 176), image_path)
        add_html(p, fitz.Rect(270, y + 31, 526, y + 147), f'<p class="kicker">0{i + 1} · {html.escape(label)}</p><p class="card-body" style="font-size:11pt; margin-top:11pt">{html.escape(body)}</p>', lang)
    add_footer(p, 4, total, lang)

    # 5. Business model
    p = new_page(doc)
    kicker, title, body = detail["model"]
    title_block(p, lang, kicker, title, body)
    p.draw_line(fitz.Point(98, 225), fitz.Point(98, 690), color=GOLD, width=2)
    for i, (label, copy) in enumerate(detail["model_steps"]):
        y = 208 + i * 166
        p.draw_circle(fitz.Point(98, y + 18), 8, color=GOLD, fill=GOLD)
        p.draw_rect(fitz.Rect(130, y, 553, y + 132), radius=0.05, color=None, fill=WHITE)
        add_html(p, fitz.Rect(158, y + 24, 525, y + 112), f'<p class="card-title">{html.escape(label)}</p><p class="card-body" style="font-size:10.5pt;margin-top:9pt">{html.escape(copy)}</p>', lang, scale_low=0.65)
    add_footer(p, 5, total, lang)

    # 6. Production
    p = new_page(doc, FOREST)
    title_block(p, lang, c["production_kicker"], c["production_title"], light=True)
    production_images = [ASSETS / "make_oem.webp", ASSETS / "make_ingredient.webp", ASSETS / "make_supply.webp"]
    for i, ((label, body), image_path) in enumerate(zip(c["production"], production_images)):
        y = 170 + i * 184
        p.draw_rect(fitz.Rect(42, y, 553, y + 160), radius=0.06, color=None, fill=GREEN)
        add_image_cover(p, fitz.Rect(42, y, 226, y + 160), image_path)
        add_html(p, fitz.Rect(252, y + 28, 526, y + 138), f'<p class="card-title white">{html.escape(label)}</p><p class="card-body soft" style="font-size:9pt; margin-top:9pt">{html.escape(body)}</p>', lang, scale_low=0.62)
    add_footer(p, 6, total, lang, light=True)

    # 7. Portfolio overview
    p = new_page(doc)
    title_block(p, lang, c["portfolio_kicker"], c["portfolio_title"], c["portfolio_subtitle"])
    for i, ((name, pack), image_path) in enumerate(zip(c["products"], PRODUCT_IMAGES.values())):
        row, col = divmod(i, 4)
        x = 42 + col * 129
        y = 182 + row * 268
        p.draw_rect(fitz.Rect(x, y, x + 113, y + 242), radius=0.06, color=None, fill=WHITE)
        add_image_fit(p, fitz.Rect(x + 5, y + 5, x + 108, y + 108), image_path)
        add_html(p, fitz.Rect(x + 12, y + 130, x + 101, y + 222), f'<p class="card-title" style="font-size:12pt">{html.escape(name)}</p><p class="label" style="margin-top:9pt">{html.escape(pack)}</p>', lang)
    add_footer(p, 7, total, lang)

    # 8. Portfolio detail
    p = new_page(doc)
    kicker, title, body = detail["categories"]
    title_block(p, lang, kicker, title, body)
    category_rows = [
        (c["products"][0], c["products"][1]),
        (c["products"][2], c["products"][4]),
        (c["products"][3], c["products"][5]),
        (c["products"][6], c["products"][7]),
    ]
    for row, pair in enumerate(category_rows):
        y = 200 + row * 132
        for col, (name, pack) in enumerate(pair):
            x = 42 + col * 261
            p.draw_rect(fitz.Rect(x, y, x + 240, y + 108), radius=0.05, color=None, fill=WHITE)
            add_html(p, fitz.Rect(x + 20, y + 22, x + 220, y + 90), f'<p class="card-title" style="font-size:13.5pt">{html.escape(name)}</p><p class="label" style="margin-top:9pt">{html.escape(pack)}</p>', lang, scale_low=0.62)
    p.draw_rect(fitz.Rect(42, 730, 553, 772), radius=0.04, color=None, fill=CREAM_2)
    add_html(p, fitz.Rect(58, 740, 537, 766), f'<p class="small" style="text-align:center">{html.escape(labels["pack_note"])}</p>', lang, scale_low=0.65)
    add_footer(p, 8, total, lang)

    # 9. Sales channels
    p = new_page(doc, FOREST)
    kicker, title, body = detail["channels"]
    title_block(p, lang, kicker, title, body, light=True)
    for i, (label, copy) in enumerate(detail["channel_items"]):
        row, col = divmod(i, 2)
        x = 42 + col * 261
        y = 220 + row * 230
        p.draw_rect(fitz.Rect(x, y, x + 240, y + 195), radius=0.06, color=None, fill=GREEN)
        add_html(p, fitz.Rect(x + 20, y + 25, x + 220, y + 168), f'<p class="kicker">0{i + 1}</p><p class="card-title white" style="font-size:14pt;margin-top:12pt">{html.escape(label)}</p><p class="card-body soft" style="font-size:9.3pt;margin-top:12pt">{html.escape(copy)}</p>', lang, scale_low=0.58)
    add_footer(p, 9, total, lang, light=True)

    # 10-12. Brand milestones — every homepage item, two years per page.
    history_spreads = [c["history"][0:2], c["history"][2:4], c["history"][4:6]]
    for spread_index, spread in enumerate(history_spreads):
        p = new_page(doc, FOREST)
        year_range = f"{spread[0][0]}–{spread[-1][0]}"
        history_heading = f'{c["history_title"]} · {year_range}'
        if LANGUAGES[lang]["dir"] == "rtl":
            history_heading = f'{c["history_title"]} | \u200e{year_range}\u200e'
        title_block(
            p,
            lang,
            c["history_kicker"],
            history_heading,
            c["history_subtitle"],
            light=True,
        )
        for col, (year, items) in enumerate(spread):
            x = 42 + col * 265
            p.draw_rect(fitz.Rect(x, 190, x + 246, 758), radius=0.06, color=None, fill=GREEN)
            list_items = []
            for item_index, item in enumerate(items):
                item_text = html.escape(item)
                if item_index == 0:
                    item_text = f'<b style="color:#ffffff">{item_text}</b>'
                list_items.append(
                    f'<li style="font-size:10pt;line-height:1.45;margin-bottom:7pt">{item_text}</li>'
                )
            markup = (
                f'<p class="metric" style="font-size:24pt">{html.escape(year)}</p>'
                f'<ul style="color:#dce2dc;margin-top:18pt;padding-inline-start:16pt">'
                f'{"".join(list_items)}</ul>'
            )
            add_html(p, fitz.Rect(x + 20, 216, x + 226, 735), markup, lang, scale_low=0.78)
        add_html(
            p,
            fitz.Rect(42, 771, 553, 799),
            f'<p class="small soft" style="font-size:7.4pt;text-align:center">{html.escape(labels["history_note"])}</p>',
            lang,
            scale_low=0.62,
        )
        add_footer(p, 10 + spread_index, total, lang, light=True)

    # 13. Partnership process
    p = new_page(doc)
    title_block(p, lang, c["partner_kicker"], c["partner_title"], c["partner_body"])
    add_image_cover(p, fitz.Rect(42, 205, 235, 475), ASSETS / "team_walk.webp")
    add_html(p, fitz.Rect(266, 228, 530, 450), f'<p class="card-title">01 · {html.escape(labels["review"])}</p><p class="card-body" style="font-size:10pt;margin-top:9pt">{html.escape(c["partner_points"][0][1])}</p><p class="card-title" style="margin-top:22pt">02 · {html.escape(labels["consult"])}</p><p class="card-body" style="font-size:10pt;margin-top:9pt">{html.escape(detail["consultation"])}</p>', lang, scale_low=0.56)
    for i, (label, body) in enumerate(c["partner_points"]):
        x = 42 + i * 171
        p.draw_rect(fitz.Rect(x, 500, x + 154, 720), radius=0.06, color=None, fill=WHITE)
        add_html(p, fitz.Rect(x + 16, 526, x + 138, 700), f'<p class="kicker">0{i + 1}</p><p class="card-title" style="font-size:13pt;margin-top:9pt">{html.escape(label)}</p><p class="card-body" style="font-size:8.7pt;margin-top:11pt">{html.escape(body)}</p>', lang, scale_low=0.52)
    add_footer(p, 13, total, lang)

    # 14. Contact
    p = new_page(doc, FOREST)
    add_logo(p, "company", fitz.Rect(42, 44, 126, 126))
    title_block(p, lang, c["contact_kicker"], c["contact_title"], c["contact_subtitle"], y=152, light=True)
    labels = c["contact_labels"]
    for i, (label, value) in enumerate(zip(labels, CONTACT_VALUES)):
        row, col = divmod(i, 2)
        x = 42 + col * 261
        y = 315 + row * 98
        add_html(p, fitz.Rect(x, y, x + 240, y + 84), f'<p class="label">{html.escape(label)}</p><p class="value white" style="font-size:9.5pt; margin-top:5pt">{html.escape(value)}</p>', lang)
        if value.startswith("http"):
            p.insert_link({"kind": fitz.LINK_URI, "from": fitz.Rect(x, y, x + 240, y + 84), "uri": value})
        elif "@" in value:
            p.insert_link({"kind": fitz.LINK_URI, "from": fitz.Rect(x, y, x + 240, y + 84), "uri": f"mailto:{value}"})
    q1 = qr_png("https://companimal.kr", "qr-company.png")
    q2 = qr_png("https://pf.kakao.com/_xnyDcs", "qr-kakao.png")
    p.draw_rect(fitz.Rect(42, 638, 137, 733), radius=0.05, color=None, fill=WHITE)
    p.draw_rect(fitz.Rect(154, 638, 249, 733), radius=0.05, color=None, fill=WHITE)
    add_image_fit(p, fitz.Rect(48, 644, 131, 727), q1)
    add_image_fit(p, fitz.Rect(160, 644, 243, 727), q2)
    add_html(p, fitz.Rect(278, 650, 553, 730), f'<p class="small soft">{html.escape(c["disclosure"])}</p>', lang)
    add_footer(p, 14, total, lang, light=True)

    doc.set_metadata({"title": c["title"], "author": "Companimal Co., Ltd.", "subject": "Company profile", "keywords": f"Companimal, ZERO LABS, {LANGUAGES[lang]['locale']}"})
    doc.subset_fonts()
    return doc


SOURCE_MASKS: dict[int, list[tuple[int, int, int, int]]] = {
    1: [(850, 55, 1055, 245), (475, 245, 1055, 390)],
    2: [(50, 18, 1018, 1328)],
    3: [
        (260, 50, 810, 175),
        (120, 365, 495, 465), (620, 365, 1000, 465),
        (120, 680, 500, 790), (620, 680, 1000, 790),
        (110, 995, 500, 1105), (615, 995, 1005, 1105),
        (80, 1290, 355, 1380), (350, 1290, 625, 1380), (665, 1290, 1035, 1380),
    ],
    4: [(55, 865, 1015, 1380)],
    5: [(55, 850, 1015, 1380)],
    6: [(55, 850, 1015, 1380)],
    7: [(55, 850, 1015, 1380)],
    8: [(460, 270, 1050, 750), (460, 845, 1050, 1325)],
    9: [(55, 860, 1015, 1380)],
    10: [(55, 850, 1015, 1380)],
    11: [(55, 850, 1015, 1380)],
    12: [(55, 850, 1015, 1380)],
    13: [(55, 925, 1015, 1380)],
    14: [(55, 925, 1015, 1380)],
    15: [(60, 35, 1005, 450), (145, 800, 485, 930), (625, 800, 1010, 930), (145, 1280, 485, 1380), (625, 1280, 1010, 1380)],
    16: [(35, 35, 1030, 600)],
}


def prepare_source_pages() -> list[Path]:
    """Rasterize and sanitize only replaceable text regions of the supplied master."""
    SOURCE_RENDER_DIR.mkdir(parents=True, exist_ok=True)
    SOURCE_SANITIZED_DIR.mkdir(parents=True, exist_ok=True)
    source = fitz.open(SOURCE_PDF)
    if len(source) != 16:
        raise RuntimeError(f"Expected 16-page source brochure, found {len(source)}")
    results: list[Path] = []
    for page_no, source_page in enumerate(source, start=1):
        rendered = SOURCE_RENDER_DIR / f"page-{page_no:02d}.png"
        sanitized = SOURCE_SANITIZED_DIR / f"page-{page_no:02d}.png"
        needs_render = not rendered.exists() or rendered.stat().st_mtime < SOURCE_PDF.stat().st_mtime
        if not needs_render:
            with Image.open(rendered) as cached:
                needs_render = cached.size != (round(SOURCE_PAGE.width), round(SOURCE_PAGE.height))
        if needs_render:
            source_page.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False).save(rendered)
        needs_sanitize = not sanitized.exists() or sanitized.stat().st_mtime < max(rendered.stat().st_mtime, Path(__file__).stat().st_mtime)
        if not needs_sanitize:
            with Image.open(sanitized) as cached:
                needs_sanitize = cached.size != (round(SOURCE_PAGE.width), round(SOURCE_PAGE.height))
        if needs_sanitize:
            with Image.open(rendered) as source_image:
                original = source_image.convert("RGB")
                cleaned = original.copy()
                fill = (105, 177, 227) if page_no in {1, 2, 16} else (255, 255, 255)
                draw = ImageDraw.Draw(cleaned)
                for bounds in SOURCE_MASKS[page_no]:
                    draw.rectangle(bounds, fill=fill)
                # Guardrail: pixels outside the declared masks must remain byte-identical.
                outside_delta = ImageChops.difference(original, cleaned)
                delta_draw = ImageDraw.Draw(outside_delta)
                for bounds in SOURCE_MASKS[page_no]:
                    delta_draw.rectangle(bounds, fill=(0, 0, 0))
                if outside_delta.getbbox() is not None:
                    raise RuntimeError(f"Source fidelity check failed on page {page_no}")
                cleaned.save(sanitized, optimize=True)
        results.append(sanitized)
    source.close()
    return results


def source_product_text(page: fitz.Page, lang: str, item: tuple[str, str, list[str], str], rect: fitz.Rect, accent: str) -> None:
    name, description, bullets, pack = item
    bullet_html = "".join(f'<li style="font-size:18pt;line-height:1.42;margin-bottom:5pt">{html.escape(value)}</li>' for value in bullets)
    markup = (
        f'<p style="font-size:18pt;font-weight:700;color:{accent}">ZERO LABS</p>'
        f'<p style="font-size:45pt;line-height:1.12;font-weight:700;margin-top:7pt">{html.escape(name)}</p>'
        f'<p style="font-size:20pt;line-height:1.5;color:#68706b;margin-top:12pt">{html.escape(description)}</p>'
        f'<ul style="margin-top:10pt">{bullet_html}</ul>'
        f'<p style="font-size:22pt;font-weight:700;color:{accent};margin-top:10pt">{html.escape(pack)}</p>'
    )
    add_html(page, rect, markup, lang, scale_low=0.42)


def product_brochure(lang: str) -> fitz.Document:
    """Localize the supplied 16-page master without replacing its product imagery."""
    c = PRODUCT_CONTENT[lang]
    backgrounds = prepare_source_pages()
    doc = fitz.open()
    for background in backgrounds:
        page = new_source_page(doc)
        page.insert_image(SOURCE_PAGE, filename=str(background), keep_proportion=True)

    # 1. Cover — keep the supplied mascot and brand artwork.
    p = doc[0]
    q = qr_png("https://companimal.kr", "qr-company.png")
    add_image_fit(p, fitz.Rect(875, 70, 1035, 230), q)
    add_html(
        p,
        fitz.Rect(485, 255, 1035, 390),
        f'<p class="white" style="font-size:34pt;line-height:1.22;font-weight:700;text-align:center">{html.escape(c["cover_tagline"])}</p>',
        lang,
        scale_low=0.48,
    )
    p.insert_link({"kind": fitz.LINK_URI, "from": fitz.Rect(875, 70, 1035, 230), "uri": "https://companimal.kr"})

    # 2. Greeting — translated copy replaces the Chinese raster text.
    p = doc[1]
    greeting = "".join(
        f'<p class="white" style="font-size:24pt;line-height:1.65;text-align:center;margin-bottom:24pt">{html.escape(paragraph)}</p>'
        for paragraph in c["greeting"]
    )
    add_html(p, fitz.Rect(90, 55, 976, 1270), f'<p class="white" style="font-size:52pt;font-weight:700;text-align:center">{html.escape(c["greeting_title"])}</p><div style="border-top:3pt solid white;margin:28pt 120pt 42pt"></div>{greeting}', lang, scale_low=0.55)

    # 3. Product index — retain every product image and rewrite only labels.
    p = doc[2]
    add_html(p, fitz.Rect(260, 62, 810, 160), f'<p style="font-size:47pt;font-weight:700;text-align:center">{html.escape(c["catalog_title"])}</p>', lang, scale_low=0.55)
    index_rects = [
        fitz.Rect(135, 375, 480, 455), fitz.Rect(635, 375, 990, 455),
        fitz.Rect(135, 690, 480, 780), fitz.Rect(635, 690, 990, 780),
        fitz.Rect(125, 1005, 480, 1095), fitz.Rect(635, 1005, 990, 1095),
        fitz.Rect(85, 1300, 345, 1403), fitz.Rect(360, 1300, 615, 1403), fitz.Rect(675, 1300, 1025, 1403),
    ]
    for label, rect in zip(c["catalog"], index_rects):
        add_html(p, rect, f'<p style="font-size:25pt;font-weight:700;text-align:center">{html.escape(label)}</p>', lang, scale_low=0.45)

    single_specs = {
        4: ("meat_1kg", "#a65b37", fitz.Rect(70, 885, 990, 1405)),
        5: ("meat_350g", "#a65b37", fitz.Rect(70, 870, 990, 1405)),
        6: ("nutrition_1kg", "#6cae4a", fitz.Rect(70, 870, 990, 1405)),
        7: ("nutrition_350g", "#6cae4a", fitz.Rect(70, 870, 990, 1405)),
        9: ("dental", "#50afd7", fitz.Rect(70, 880, 990, 1405)),
        10: ("meatless", "#835b95", fitz.Rect(70, 870, 990, 1405)),
        11: ("berry_1kg", "#bc4375", fitz.Rect(70, 870, 990, 1405)),
        12: ("berry_400g", "#bc4375", fitz.Rect(70, 870, 990, 1405)),
        13: ("baked_1kg", "#ef8e27", fitz.Rect(70, 945, 990, 1405)),
        14: ("baked_200g", "#ef8e27", fitz.Rect(70, 945, 990, 1405)),
    }
    for page_no, (product_key, accent, rect) in single_specs.items():
        source_product_text(doc[page_no - 1], lang, c["products"][product_key], rect, accent)

    source_product_text(doc[7], lang, c["products"]["fresh_ring"], fitz.Rect(510, 295, 1000, 735), "#ea674a")
    source_product_text(doc[7], lang, c["products"]["mungs"], fitz.Rect(510, 870, 1000, 1310), "#8a5e38")

    # 15. Trial packs — preserve all four photographed packs.
    p = doc[14]
    add_html(p, fitz.Rect(75, 48, 990, 245), f'<p style="font-size:46pt;font-weight:700;color:#54afe0">{html.escape(c["trial_title"])}</p><p style="font-size:22pt;line-height:1.45;color:#68706b;margin-top:12pt">{html.escape(c["trial_intro"])}</p>', lang, scale_low=0.5)
    trial_keys = ["meat_350g", "nutrition_350g", "berry_400g", "baked_200g"]
    trial_rects = [fitz.Rect(155, 820, 475, 920), fitz.Rect(640, 820, 1000, 920), fitz.Rect(155, 1300, 475, 1410), fitz.Rect(640, 1300, 1000, 1410)]
    trial_colors = ["#a65b37", "#6cae4a", "#bc4375", "#ef8e27"]
    for key, rect, color in zip(trial_keys, trial_rects, trial_colors):
        name = c["products"][key][0]
        add_html(p, rect, f'<p style="font-size:24pt;font-weight:700;text-align:center;color:{color}">{html.escape(name)}</p><p style="font-size:18pt;text-align:center;color:#68706b;margin-top:4pt">30 g</p>', lang, scale_low=0.45)

    # 16. Verified contact channels replace all stale contact and QR pixels.
    p = doc[15]
    add_html(p, fitz.Rect(55, 55, 660, 205), f'<p class="white" style="font-size:43pt;font-weight:700">{html.escape(c["contact_title"])}</p><p class="white" style="font-size:20pt;line-height:1.45;margin-top:10pt">{html.escape(c["contact_intro"])}</p>', lang, scale_low=0.52)
    for i, (label, value) in enumerate(zip(c["contact_labels"], PRODUCT_CONTACT_VALUES)):
        y = 250 + i * 76
        add_html(p, fitz.Rect(60, y, 690, y + 68), f'<p style="font-size:16pt;font-weight:700;color:#ffffff">{html.escape(label)}</p><p class="white" style="font-size:16pt;margin-top:3pt">{html.escape(value)}</p>', lang, scale_low=0.45)
        uri = f"mailto:{value}" if "@" in value else value if value.startswith("http") else None
        if uri:
            p.insert_link({"kind": fitz.LINK_URI, "from": fitz.Rect(60, y, 690, y + 68), "uri": uri})
    q1 = qr_png("https://companimal.kr", "qr-company.png")
    q2 = qr_png("https://pf.kakao.com/_xnyDcs", "qr-kakao.png")
    p.draw_rect(fitz.Rect(780, 120, 990, 330), color=None, fill=WHITE)
    p.draw_rect(fitz.Rect(780, 355, 990, 565), color=None, fill=WHITE)
    add_image_fit(p, fitz.Rect(792, 132, 978, 318), q1)
    add_image_fit(p, fitz.Rect(792, 367, 978, 553), q2)
    p.insert_link({"kind": fitz.LINK_URI, "from": fitz.Rect(780, 120, 990, 330), "uri": "https://companimal.kr"})
    p.insert_link({"kind": fitz.LINK_URI, "from": fitz.Rect(780, 355, 990, 565), "uri": "https://pf.kakao.com/_xnyDcs"})

    doc.set_metadata({"title": c["title"], "author": "Companimal Co., Ltd.", "subject": "ZERO LABS product brochure — localized from the supplied 16-page master", "keywords": f"ZERO LABS, dog treats, {LANGUAGES[lang]['locale']}"})
    doc.subset_fonts()
    return doc


def save_with_language(doc: fitz.Document, path: Path, locale: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = path.with_suffix(".raw.pdf")
    doc.save(raw, garbage=4, deflate=True, clean=True)
    doc.close()
    reader = PdfReader(str(raw))
    writer = PdfWriter()
    writer.append_pages_from_reader(reader)
    if reader.metadata:
        writer.add_metadata({k: str(v) for k, v in reader.metadata.items() if v is not None})
    writer._root_object.update({NameObject("/Lang"): TextStringObject(locale)})
    with path.open("wb") as handle:
        writer.write(handle)
    raw.unlink()


def render_pdf(path: Path) -> list[Path]:
    target = RENDER_DIR / path.stem
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    doc = fitz.open(path)
    results = []
    matrix = fitz.Matrix(1.45, 1.45)
    for index, page in enumerate(doc):
        out = target / f"page-{index + 1:02d}.png"
        page.get_pixmap(matrix=matrix, alpha=False).save(out)
        results.append(out)
    doc.close()
    return results


def contact_sheet(images: list[Path], output: Path, columns: int = 4) -> None:
    thumbs = []
    for path in images:
        image = Image.open(path).convert("RGB")
        image.thumbnail((220, 310))
        thumbs.append(image.copy())
    rows = (len(thumbs) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * 230, rows * 320), "white")
    for i, image in enumerate(thumbs):
        x = (i % columns) * 230 + 5
        y = (i // columns) * 320 + 5
        sheet.paste(image, (x, y))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, quality=92)


def build(languages: list[str]) -> dict[str, dict[str, object]]:
    prepare_font_files()
    ensure_inputs()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    if set(languages) == set(LANGUAGES):
        for pattern in ("company-profile-*.pdf", "product-brochure-*.pdf"):
            for stale in OUTPUT.glob(pattern):
                stale.unlink()
    results: dict[str, dict[str, object]] = {}
    for lang in languages:
        company_path = OUTPUT / f"company-profile-{lang}-2026-v3.pdf"
        product_path = OUTPUT / f"product-brochure-{lang}-2026-v2.pdf"
        save_with_language(company_brochure(lang), company_path, LANGUAGES[lang]["locale"])
        save_with_language(product_brochure(lang), product_path, LANGUAGES[lang]["locale"])
        company_renders = render_pdf(company_path)
        product_renders = render_pdf(product_path)
        company_sheet = RENDER_DIR / f"company-profile-{lang}-contact-sheet.png"
        product_sheet = RENDER_DIR / f"product-brochure-{lang}-contact-sheet.png"
        contact_sheet(company_renders, company_sheet)
        contact_sheet(product_renders, product_sheet)
        results[lang] = {
            "label": LANGUAGES[lang]["label"],
            "label_ko": LANGUAGES[lang]["label_ko"],
            "locale": LANGUAGES[lang]["locale"],
            "company": {"path": str(company_path.relative_to(ROOT)), "bytes": company_path.stat().st_size, "pages": len(company_renders)},
            "product": {"path": str(product_path.relative_to(ROOT)), "bytes": product_path.stat().st_size, "pages": len(product_renders)},
        }
    if "ko" in languages:
        shutil.copy2(RENDER_DIR / "company-profile-ko-contact-sheet.png", OUTPUT / "company-profile-preview-ko.png")
    manifest = OUTPUT / "brochure-files.json"
    manifest.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--languages", nargs="+", default=list(LANGUAGES), choices=list(LANGUAGES))
    args = parser.parse_args()
    print(json.dumps(build(args.languages), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

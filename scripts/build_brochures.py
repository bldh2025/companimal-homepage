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
import os
import re
import shutil
import unicodedata
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
COMPANY_PAGE = fitz.Rect(0, 0, 842, 595)
SOURCE_PAGE = fitz.Rect(0, 0, 1066, 1492)
FOREST = (22 / 255, 36 / 255, 26 / 255)
GREEN = (31 / 255, 51 / 255, 37 / 255)
MID_GREEN = (44 / 255, 70 / 255, 50 / 255)
CREAM = (245 / 255, 241 / 255, 232 / 255)
CREAM_2 = (236 / 255, 230 / 255, 214 / 255)
GOLD = (216 / 255, 179 / 255, 106 / 255)
WHITE = (1, 1, 1)
SAGE = (190 / 255, 203 / 255, 190 / 255)
PALE_GREEN = (225 / 255, 232 / 255, 223 / 255)

CONTACT_VALUES = [
    "https://companimal.kr",
    "https://zerolabs.co.kr",
    "https://제로랩스.com",
    "https://pf.kakao.com/_xnyDcs",
    "bldh2025@naver.com",
    "Unit 215-26, 30 Namdong-seoro 236beon-gil, Namdong-gu, Incheon, Republic of Korea",
]

CONTACT_URIS = [
    "https://companimal.kr",
    "https://zerolabs.co.kr",
    "https://xn--yj2b7mx8w6tf.com/#",
    "https://pf.kakao.com/_xnyDcs",
    "mailto:bldh2025@naver.com",
    None,
]

CHANNEL_URLS = [
    "https://zerolabs.co.kr/",
    "https://www.coupang.com/np/search?component=&q=%EC%A0%9C%EB%A1%9C%EB%9E%A9%EC%8A%A4&traceId=mr3oy0ab&channel=user",
    "https://xn--yj2b7mx8w6tf.com/#",
    "https://smartstore.naver.com/zerolabs",
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
        "categories": ("PORTFOLIO DETAIL", "간식 유형과 포장 단위로 정리한 제품 라인업", "져키·덴탈·베이크드·식물성·시리얼 타입을 대용량과 소용량으로 구성해 고객과 채널별 제안 폭을 넓혔습니다."),
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

DONATION_AMOUNT_LABELS = {
    "ko": "64,762,460원",
    "en": "64,762,460 KRW",
    "zh-hans": "64,762,460韩元",
    "zh-hant": "64,762,460韓元",
    "ja": "64,762,460ウォン",
    "th": "64,762,460 วอน",
    "ar": "64,762,460 وون",
}

COMPANY_A_UI = {
    "ko": {"process": "기획 → OEM → 제품 정보 → 공급", "routes": "B2C · B2B · 오픈마켓 · 도매"},
    "en": {"process": "PLAN → OEM → PRODUCT INFORMATION → SUPPLY", "routes": "B2C · B2B · MARKETPLACE · WHOLESALE"},
    "zh-hans": {"process": "企划 → OEM → 产品信息 → 供货", "routes": "B2C · B2B · 电商平台 · 批发"},
    "zh-hant": {"process": "企劃 → OEM → 產品資訊 → 供貨", "routes": "B2C · B2B · 電商平台 · 批發"},
    "ja": {"process": "企画 → OEM → 商品情報 → 供給", "routes": "B2C · B2B · モール · 卸売"},
    "th": {"process": "วางแผน → OEM → ข้อมูลสินค้า → จัดส่ง", "routes": "B2C · B2B · มาร์เก็ตเพลส · ขายส่ง"},
    "ar": {"process": "التخطيط ← OEM ← معلومات المنتج ← التوريد", "routes": "B2C · B2B · الأسواق الإلكترونية · الجملة"},
}

BRAND_PROOF = {
    "ko": {
        "kicker": "BRAND PROOF",
        "title": "숫자로 확인하는 브랜드의 발자취",
        "subtitle": "브랜드가 공개한 연혁의 주요 기록입니다. 2025년 이전 브랜드 이력과 이후 반려동행 운영 이력을 구분합니다.",
        "items": [
            ("64,762,460원", "2024년 유기견 임보처 사단법인 기부 기록"),
            ("4개 지역", "대만·베트남·홍콩·필리핀 수출 이력"),
            ("3년", "2021–2023 K-PET 참가 기록"),
            ("TOP 3", "2026년 쿠팡 간식 판매량 기록"),
        ],
    },
    "en": {
        "kicker": "BRAND PROOF",
        "title": "A track record expressed in numbers",
        "subtitle": "Selected milestones published by the brand. Records before 2025 and Companimal operations thereafter are identified separately.",
        "items": [
            ("KRW 64.76M", "Donation record to a foster-care nonprofit in 2024"),
            ("4 markets", "Export milestones: Taiwan, Vietnam, Hong Kong and the Philippines"),
            ("3 years", "K-PET participation recorded from 2021 to 2023"),
            ("TOP 3", "Coupang treat sales-volume record in 2026"),
        ],
    },
    "zh-hans": {
        "kicker": "品牌实绩",
        "title": "用数字呈现品牌历程",
        "subtitle": "以下为品牌公开历程中的主要记录，并区分2025年前品牌经历与此后的 Companimal 运营记录。",
        "items": [
            ("64,762,460韩元", "2024年向流浪犬寄养公益机构捐赠记录"),
            ("4个地区", "中国台湾、越南、中国香港、菲律宾出口记录"),
            ("3年", "2021–2023年 K-PET 参展记录"),
            ("TOP 3", "2026年 Coupang 零食销量记录"),
        ],
    },
    "zh-hant": {
        "kicker": "品牌實績",
        "title": "以數字呈現品牌歷程",
        "subtitle": "以下為品牌公開歷程中的主要紀錄，並區分2025年前品牌經歷與此後的 Companimal 營運紀錄。",
        "items": [
            ("64,762,460韓元", "2024年向流浪犬寄養公益機構捐贈紀錄"),
            ("4個地區", "臺灣、越南、香港、菲律賓出口紀錄"),
            ("3年", "2021–2023年 K-PET 參展紀錄"),
            ("TOP 3", "2026年 Coupang 零食銷量紀錄"),
        ],
    },
    "ja": {
        "kicker": "BRAND PROOF",
        "title": "数字で見るブランドの歩み",
        "subtitle": "ブランドが公開した沿革の主な記録です。2025年以前と、それ以降のCompanimal運営実績を区分しています。",
        "items": [
            ("64,762,460ウォン", "2024年の保護犬支援団体への寄付記録"),
            ("4地域", "台湾・ベトナム・香港・フィリピンへの輸出記録"),
            ("3年間", "2021–2023年のK-PET出展記録"),
            ("TOP 3", "2026年Coupangおやつ販売量記録"),
        ],
    },
    "th": {
        "kicker": "ผลงานของแบรนด์",
        "title": "เส้นทางของแบรนด์ในรูปตัวเลข",
        "subtitle": "หมุดหมายสำคัญที่แบรนด์เผยแพร่ โดยแยกประวัติก่อนปี 2025 และการดำเนินงานของ Companimal หลังจากนั้น",
        "items": [
            ("64,762,460 วอน", "บันทึกการบริจาคให้องค์กรช่วยเหลือสุนัขในปี 2024"),
            ("4 ตลาด", "บันทึกการส่งออกไปไต้หวัน เวียดนาม ฮ่องกง และฟิลิปปินส์"),
            ("3 ปี", "บันทึกการเข้าร่วม K-PET ระหว่างปี 2021–2023"),
            ("TOP 3", "บันทึกยอดขายขนมบน Coupang ในปี 2026"),
        ],
    },
    "ar": {
        "kicker": "إثبات العلامة",
        "title": "مسيرة العلامة بالأرقام",
        "subtitle": "محطات مختارة من السجل المنشور للعلامة، مع فصل ما قبل 2025 عن عمليات Companimal اللاحقة.",
        "items": [
            ("64,762,460 وون", "سجل تبرع لجهة ترعى الكلاب في عام 2024"),
            ("4 أسواق", "سجل تصدير إلى تايوان وفيتنام وهونغ كونغ والفلبين"),
            ("3 سنوات", "سجل مشاركة K-PET بين 2021 و2023"),
            ("TOP 3", "سجل حجم مبيعات الوجبات الخفيفة على Coupang في 2026"),
        ],
    },
}

HOMEPAGE_COMPANY = {
    "ko": {
        "ceo": ("대표 인사말", "좋은 간식의 기본에 더 집중합니다", "반려견이 매일 먹는 간식인 만큼, 저희는 좋은 원료와 정직한 레시피라는 기본에 더 집중합니다. 보호자와 파트너 모두가 믿고 오래 함께할 수 있는 브랜드를 만들겠습니다.", "장성환", "대표이사 · 주식회사 반려동행"),
        "team": ("TEAM", "우리는 매일 '동행'을 연습합니다", "반려동행이라는 이름처럼, 제로랩스 팀은 같은 옷을 입고 같은 방향으로 걷습니다. 좋은 간식은 결국 함께 일하는 사람들에게서 나온다고 믿습니다."),
        "profile": ("COMPANY PROFILE", "거래 검토에 필요한 회사 정보", "브랜드와 운영 채널을 명확히 공개해 파트너가 기본 정보를 빠르게 확인할 수 있도록 합니다.", [
            ("브랜드", "제로랩스", "ZERO LABS"),
            ("회사명", "주식회사 반려동행", "대표 : 장성환"),
            ("사업", "반려견 간식", "반려동물 식품·제품 유통"),
            ("채널", "B2C · B2B", "쿠팡 · 스마트스토어 운영"),
            ("사업자등록번호", "266-88-03624", "대한민국 법인"),
            ("주소", "인천광역시 남동구 남동서로236번길 30, 215-26호", "논현동 · 논현2차푸르지오시티"),
        ]),
        "donation": ("DONATION CAMPAIGN", "함께 걷는 마음을 기부로 이어갑니다", "제품과 유통 성과뿐 아니라 반려견의 더 나은 일상을 위한 나눔의 기록도 함께 쌓아왔습니다.", "유기견 임보처 사단법인 1년간 기부 기록", [("브랜드가 함께한 나눔", "제로랩스는 제품을 넘어 반려견과 보호자가 함께 살아가는 환경을 함께 바라봅니다."), ("계속 이어갈 책임", "주식회사 반려동행은 브랜드를 이어받아 신뢰받는 제품과 책임 있는 활동을 함께 쌓아가겠습니다.")]),
    },
    "en": {
        "ceo": ("CEO MESSAGE", "Focused on the fundamentals of better treats", "Because dogs enjoy treats every day, we focus on the fundamentals: good ingredients and honest recipes. We will build a brand that pet parents and partners can trust for the long term.", "Seonghwan Jang", "CEO · Companimal Co., Ltd."),
        "team": ("TEAM", "We practice walking together every day", "True to the name Companimal, the ZERO LABS team wears the same shirts and walks in the same direction. We believe better treats begin with the people who work together."),
        "profile": ("COMPANY PROFILE", "Essential information for partner review", "We publish our brand and operating channels clearly so partners can review the essentials quickly.", [
            ("Brand", "ZERO LABS", "Dog-treat brand"),
            ("Company", "Companimal Co., Ltd.", "Representative : Seonghwan Jang"),
            ("Business", "Dog treats", "Pet food and product distribution"),
            ("Channels", "B2C · B2B", "Coupang · Naver Smart Store"),
            ("Registration No.", "266-88-03624", "Republic of Korea"),
            ("Address", "Unit 215-26, 30 Namdong-seoro 236beon-gil", "Namdong-gu, Incheon, Republic of Korea"),
        ]),
        "donation": ("DONATION CAMPAIGN", "Turning the spirit of companionship into giving", "Alongside product and distribution milestones, the brand has built a record of support for better lives with dogs.", "One-year donation record to a nonprofit supporting foster dogs", [("Giving with the brand", "ZERO LABS looks beyond products to the environment shared by dogs and their families."), ("A responsibility we will continue", "Companimal carries the brand forward with trusted products and responsible action.")]),
    },
    "zh-hans": {
        "ceo": ("代表致辞", "更专注于优质零食的基本原则", "狗狗每天都会吃零食，因此我们更加专注于优质原料与诚实配方。我们将打造一个让宠物家长和合作伙伴都能长期信赖的品牌。", "张成焕", "代表理事 · Companimal Co., Ltd."),
        "team": ("团队", "每天练习并肩同行", "正如 Companimal 的名字，ZERO LABS 团队穿着相同的衣服，朝着同一方向前进。我们相信，好零食最终来自一起工作的人。"),
        "profile": ("公司资料", "合作审核所需的基本信息", "我们清楚公开品牌与运营渠道，让合作伙伴能够快速确认基本信息。", [
            ("品牌", "ZERO LABS", "狗狗零食品牌"),
            ("公司名称", "Companimal Co., Ltd.", "代表 : 张成焕"),
            ("业务", "狗狗零食", "宠物食品与用品流通"),
            ("渠道", "B2C · B2B", "Coupang · Naver Smart Store"),
            ("营业执照号", "266-88-03624", "韩国法人"),
            ("地址", "仁川广域市南洞区南洞西路236番街30, 215-26号", "韩国仁川"),
        ]),
        "donation": ("公益行动", "将同行的心意延续为捐赠", "品牌不仅积累产品与流通成果，也持续记录为狗狗创造更好生活的公益行动。", "向流浪犬寄养公益机构连续一年捐赠记录", [("品牌参与的公益", "ZERO LABS 不只关注产品，也关注狗狗与宠物家庭共同生活的环境。"), ("持续承担责任", "Companimal 将继续以可信赖的产品和负责任的行动运营品牌。")]),
    },
    "zh-hant": {
        "ceo": ("代表致辭", "更專注於優質零食的基本原則", "狗狗每天都會吃零食，因此我們更專注於優質原料與誠實配方。我們將打造一個讓飼主與合作夥伴都能長期信賴的品牌。", "張成煥", "代表理事 · Companimal Co., Ltd."),
        "team": ("團隊", "每天練習並肩同行", "正如 Companimal 的名字，ZERO LABS 團隊穿著相同的衣服，朝著同一方向前進。我們相信，好零食最終來自一起工作的人。"),
        "profile": ("公司資料", "合作審核所需的基本資訊", "我們清楚公開品牌與營運通路，讓合作夥伴能快速確認基本資訊。", [
            ("品牌", "ZERO LABS", "狗狗零食品牌"),
            ("公司名稱", "Companimal Co., Ltd.", "代表 : 張成煥"),
            ("業務", "狗狗零食", "寵物食品與用品流通"),
            ("通路", "B2C · B2B", "Coupang · Naver Smart Store"),
            ("營業登記號", "266-88-03624", "韓國法人"),
            ("地址", "仁川廣域市南洞區南洞西路236番街30, 215-26號", "韓國仁川"),
        ]),
        "donation": ("公益行動", "將同行的心意延續為捐贈", "品牌不只累積產品與流通成果，也持續記錄為狗狗創造更好生活的公益行動。", "向流浪犬寄養公益機構連續一年捐贈紀錄", [("品牌參與的公益", "ZERO LABS 不只關注產品，也關注狗狗與飼主共同生活的環境。"), ("持續承擔責任", "Companimal 將繼續以可信賴的產品和負責任的行動營運品牌。")]),
    },
    "ja": {
        "ceo": ("代表メッセージ", "良いおやつの基本に、さらに向き合います", "毎日口にするおやつだからこそ、良い原料と誠実なレシピという基本を大切にします。飼い主とパートナーが長く信頼できるブランドをつくります。", "チャン・ソンファン", "代表取締役 · Companimal Co., Ltd."),
        "team": ("TEAM", "私たちは毎日『同行』を実践します", "Companimal の名の通り、ZERO LABS チームは同じ服を着て同じ方向へ歩きます。良いおやつは、共に働く人から生まれると考えています。"),
        "profile": ("COMPANY PROFILE", "取引検討に必要な会社情報", "ブランドと運営チャネルを明確に公開し、パートナーが基本情報をすぐ確認できるようにします。", [
            ("ブランド", "ZERO LABS", "犬用おやつブランド"),
            ("会社名", "Companimal Co., Ltd.", "代表 : チャン・ソンファン"),
            ("事業", "犬用おやつ", "ペットフード・用品流通"),
            ("チャネル", "B2C · B2B", "Coupang · Naver Smart Store"),
            ("事業者登録番号", "266-88-03624", "韓国法人"),
            ("住所", "仁川広域市南洞区南洞西路236番ギル30, 215-26号", "韓国・仁川"),
        ]),
        "donation": ("DONATION CAMPAIGN", "共に歩む思いを寄付へ", "商品と流通の実績だけでなく、犬たちのより良い日常を支える活動も積み重ねてきました。", "保護犬の一時預かり支援団体への1年間の寄付記録", [("ブランドと共に行う支援", "ZERO LABS は商品を超え、犬と家族が共に暮らす環境に目を向けます。"), ("続けていく責任", "Companimal は信頼される商品と責任ある活動を共に積み重ねます。")]),
    },
    "th": {
        "ceo": ("สารจากผู้บริหาร", "ใส่ใจกับพื้นฐานของขนมที่ดี", "เพราะสุนัขกินขนมทุกวัน เราจึงให้ความสำคัญกับวัตถุดิบที่ดีและสูตรที่ซื่อตรง เราจะสร้างแบรนด์ที่เจ้าของสัตว์เลี้ยงและพันธมิตรไว้วางใจได้ในระยะยาว", "จาง ซองฮวาน", "ประธานเจ้าหน้าที่บริหาร · Companimal Co., Ltd."),
        "team": ("TEAM", "เราฝึกเดินไปด้วยกันทุกวัน", "ตามความหมายของชื่อ Companimal ทีม ZERO LABS สวมเสื้อแบบเดียวกันและเดินไปในทิศทางเดียวกัน เราเชื่อว่าขนมที่ดีเริ่มจากคนที่ทำงานร่วมกัน"),
        "profile": ("ข้อมูลบริษัท", "ข้อมูลสำคัญสำหรับการพิจารณาธุรกิจ", "เราเปิดเผยแบรนด์และช่องทางดำเนินงานอย่างชัดเจนเพื่อให้พันธมิตรตรวจสอบข้อมูลพื้นฐานได้รวดเร็ว", [
            ("แบรนด์", "ZERO LABS", "แบรนด์ขนมสุนัข"),
            ("ชื่อบริษัท", "Companimal Co., Ltd.", "ผู้แทน : จาง ซองฮวาน"),
            ("ธุรกิจ", "ขนมสุนัข", "จำหน่ายอาหารและผลิตภัณฑ์สัตว์เลี้ยง"),
            ("ช่องทาง", "B2C · B2B", "Coupang · Naver Smart Store"),
            ("เลขทะเบียนธุรกิจ", "266-88-03624", "นิติบุคคลเกาหลี"),
            ("ที่อยู่", "Unit 215-26, 30 Namdong-seoro 236beon-gil", "Namdong-gu, Incheon, Korea"),
        ]),
        "donation": ("กิจกรรมบริจาค", "เปลี่ยนหัวใจแห่งการร่วมทางเป็นการให้", "นอกจากผลงานด้านสินค้าและการจัดจำหน่าย แบรนด์ยังสั่งสมประวัติการสนับสนุนชีวิตที่ดีขึ้นของสุนัข", "บันทึกการบริจาคหนึ่งปีให้องค์กรช่วยเหลือสุนัข", [("การให้ร่วมกับแบรนด์", "ZERO LABS มองไกลกว่าสินค้าไปถึงสภาพแวดล้อมที่สุนัขและครอบครัวใช้ชีวิตร่วมกัน"), ("ความรับผิดชอบที่เราจะสานต่อ", "Companimal จะเดินหน้าแบรนด์ด้วยสินค้าที่น่าเชื่อถือและการดำเนินงานที่รับผิดชอบ")]),
    },
    "ar": {
        "ceo": ("رسالة الرئيس التنفيذي", "نركز أكثر على أساسيات الوجبات الجيدة", "لأن الكلاب تتناول الوجبات الخفيفة يوميا، نركز على الأساسيات: مكونات جيدة ووصفات صادقة. سنبني علامة يثق بها أصحاب الحيوانات والشركاء على المدى الطويل.", "سونغهوان جانغ", "الرئيس التنفيذي · Companimal Co., Ltd."),
        "team": ("الفريق", "نتدرب كل يوم على السير معا", "وفاء لاسم Companimal، يرتدي فريق ZERO LABS القمصان نفسها ويسير في الاتجاه نفسه. ونؤمن بأن الوجبات الأفضل تبدأ من الأشخاص الذين يعملون معا."),
        "profile": ("ملف الشركة", "المعلومات الأساسية لمراجعة الشراكة", "نوضح العلامة وقنوات التشغيل حتى يتمكن الشركاء من مراجعة المعلومات الأساسية بسرعة.", [
            ("العلامة", "ZERO LABS", "علامة وجبات خفيفة للكلاب"),
            ("اسم الشركة", "Companimal Co., Ltd.", "الممثل : سونغهوان جانغ"),
            ("النشاط", "وجبات خفيفة للكلاب", "توزيع أغذية ومنتجات الحيوانات"),
            ("القنوات", "B2C · B2B", "Coupang · Naver Smart Store"),
            ("رقم التسجيل", "266-88-03624", "شركة كورية"),
            ("العنوان", "Unit 215-26, 30 Namdong-seoro 236beon-gil", "Namdong-gu, Incheon, Korea"),
        ]),
        "donation": ("حملة التبرع", "نحوّل روح الرفقة إلى عطاء", "إلى جانب إنجازات المنتجات والتوزيع، بنت العلامة سجلا من الدعم لحياة أفضل مع الكلاب.", "سجل تبرع لمدة عام لجهة تدعم رعاية الكلاب", [("العطاء مع العلامة", "تنظر ZERO LABS إلى ما هو أبعد من المنتجات، إلى البيئة التي تجمع الكلاب وعائلاتها."), ("مسؤولية سنواصلها", "تواصل Companimal العلامة بمنتجات موثوقة وعمل مسؤول.")]),
    },
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
        ASSETS / "ceo_jangseonghwan.webp",
        ASSETS / "tee_black.webp",
        ASSETS / "tee_white.webp",
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


def thai_soft_breaks_markup(markup: str) -> str:
    """Add sparse break opportunities to Thai text nodes without touching tags."""
    leading_vowels = "เแโใไ"
    dependent_spacing_vowels = "ะาำๅ"
    parts = re.split(r"(<[^>]+>)", markup)
    for part_index in range(0, len(parts), 2):
        text = parts[part_index]
        output: list[str] = []
        thai_bases = 0
        for index, char in enumerate(text):
            output.append(char)
            if char.isspace():
                thai_bases = 0
                continue
            if "\u0e00" <= char <= "\u0e7f" and not unicodedata.category(char).startswith("M"):
                thai_bases += 1
            next_char = text[index + 1] if index + 1 < len(text) else ""
            next_is_mark = bool(next_char) and unicodedata.category(next_char).startswith("M")
            if (
                thai_bases >= 8
                and char not in leading_vowels
                and next_char not in dependent_spacing_vowels
                and not next_is_mark
            ):
                output.append("\u200b")
                thai_bases = 0
        parts[part_index] = "".join(output)
    return "".join(parts)


def add_html(page: fitz.Page, rect: fitz.Rect, markup: str, lang: str, *, scale_low: float = 0.68) -> None:
    if lang == "th":
        markup = thai_soft_breaks_markup(markup)
    css, archive = css_for(lang)
    spare, scale = page.insert_htmlbox(rect, markup, css=css, archive=archive, scale_low=scale_low)
    if spare < -0.01:
        raise RuntimeError(f"Text overflow on page {page.number + 1}: spare={spare}, scale={scale}")


def measure_html_height(markup: str, lang: str, width: float, *, max_height: float = 600) -> float:
    """Measure localized HTML at full scale before assigning a visible card."""
    if lang == "th":
        markup = thai_soft_breaks_markup(markup)
    css, archive = css_for(lang)
    scratch = fitz.open()
    page = scratch.new_page(width=width, height=max_height)
    spare, scale = page.insert_htmlbox(
        fitz.Rect(0, 0, width, max_height),
        markup,
        css=css,
        archive=archive,
        scale_low=1,
    )
    scratch.close()
    if spare < -0.01 or scale < 0.999:
        raise RuntimeError(f"Text measurement overflow for {lang}: spare={spare}, scale={scale}")
    return max_height - spare


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


def new_company_page(doc: fitz.Document, fill: tuple[float, float, float] = CREAM) -> fitz.Page:
    page = doc.new_page(width=COMPANY_PAGE.width, height=COMPANY_PAGE.height)
    page.draw_rect(COMPANY_PAGE, color=None, fill=fill)
    return page


def company_footer(page: fitz.Page, page_no: int, total: int, lang: str, *, light: bool = False) -> None:
    color = "#dce2dc" if light else "#657268"
    add_html(
        page,
        fitz.Rect(48, 558, 550, 579),
        f'<p class="small" style="font-size:7.5pt;color:{color}">ZERO LABS · Companimal Co., Ltd.</p>',
        lang,
        scale_low=1,
    )
    add_html(
        page,
        fitz.Rect(746, 558, 794, 579),
        f'<p class="small" style="font-size:7.5pt;color:{color};text-align:right">{page_no:02d} / {total:02d}</p>',
        lang,
        scale_low=1,
    )


def company_title(
    page: fitz.Page,
    lang: str,
    kicker: str,
    title: str,
    subtitle: str = "",
    *,
    light: bool = False,
    x: float = 48,
    y: float = 36,
    width: float = 746,
    height: float = 102,
    title_size: float = 25,
) -> None:
    title_class = "white" if light else ""
    subtitle_color = "#dce2dc" if light else "#506056"
    markup = (
        f'<p class="kicker">{html.escape(kicker)}</p>'
        f'<p class="{title_class}" style="font-size:{title_size}pt;line-height:1.13;font-weight:700;margin-top:7pt">{html.escape(title)}</p>'
    )
    if subtitle:
        markup += f'<p style="font-size:9.5pt;line-height:1.45;color:{subtitle_color};margin-top:8pt">{html.escape(subtitle)}</p>'
    add_html(page, fitz.Rect(x, y, x + width, y + height), markup, lang, scale_low=0.9)


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
    add_image_cover(p, fitz.Rect(42, 390, 352, 755), ASSETS / "team_walk.webp")
    p.draw_rect(fitz.Rect(374, 390, 553, 755), radius=0.05, color=None, fill=FOREST)
    add_logo(p, "company", fitz.Rect(394, 497, 533, 648))
    add_footer(p, 2, total, lang)

    # 3. Company identity
    p = new_page(doc, FOREST)
    kicker, title, body = detail["identity"]
    title_block(p, lang, kicker, title, body, light=True)
    add_image_cover(p, fitz.Rect(42, 205, 553, 430), ASSETS / "hero-dog-treats.webp")
    identity_rtl = LANGUAGES[lang]["dir"] == "rtl"
    for i, (label, copy) in enumerate(detail["identity_points"]):
        y = 460 + i * 92
        p.draw_rect(fitz.Rect(42, y, 553, y + 78), radius=0.06, color=None, fill=GREEN)
        if identity_rtl:
            number_rect = fitz.Rect(485, y + 22, 530, y + 60)
            title_rect = fitz.Rect(315, y + 17, 465, y + 63)
            copy_rect = fitz.Rect(65, y + 14, 295, y + 66)
        else:
            number_rect = fitz.Rect(62, y + 22, 102, y + 60)
            title_rect = fitz.Rect(118, y + 17, 295, y + 63)
            copy_rect = fitz.Rect(315, y + 14, 530, y + 66)
        add_html(p, number_rect, f'<p class="kicker">0{i + 1}</p>', lang, scale_low=1)
        add_html(p, title_rect, f'<p class="card-title white" style="font-size:13pt">{html.escape(label)}</p>', lang, scale_low=0.9)
        add_html(p, copy_rect, f'<p class="card-body soft" style="font-size:8.8pt">{html.escape(copy)}</p>', lang, scale_low=0.9)
    add_footer(p, 3, total, lang, light=True)

    # 4. Principles
    p = new_page(doc)
    title_block(p, lang, c["principles_kicker"], c["principles_title"])
    principle_images = [ASSETS / "approach_remove.webp", ASSETS / "approach_balance.webp", ASSETS / "hero-dog-treats.webp"]
    for i, ((label, body), image_path) in enumerate(zip(c["principles"], principle_images)):
        y = 180 + i * 195
        p.draw_rect(fitz.Rect(42, y, 553, y + 120), radius=0.08, color=None, fill=WHITE)
        add_image_fit(p, fitz.Rect(42, y + 10, 245, y + 110), image_path)
        add_html(p, fitz.Rect(270, y + 19, 526, y + 101), f'<p class="kicker">0{i + 1} · {html.escape(label)}</p><p class="card-body" style="font-size:11pt; margin-top:11pt">{html.escape(body)}</p>', lang)
    add_footer(p, 4, total, lang)

    # 5. Business model
    p = new_page(doc)
    kicker, title, body = detail["model"]
    title_block(p, lang, kicker, title, body)
    p.draw_line(fitz.Point(98, 226), fitz.Point(98, 558), color=GOLD, width=2)
    for i, (label, copy) in enumerate(detail["model_steps"]):
        y = 208 + i * 166
        p.draw_circle(fitz.Point(98, y + 18), 8, color=GOLD, fill=GOLD)
        p.draw_rect(fitz.Rect(130, y, 553, y + 108), radius=0.05, color=None, fill=WHITE)
        add_html(p, fitz.Rect(158, y + 18, 525, y + 92), f'<p class="card-title">{html.escape(label)}</p><p class="card-body" style="font-size:10.5pt;margin-top:9pt">{html.escape(copy)}</p>', lang, scale_low=0.72)
    add_footer(p, 5, total, lang)

    # 6. Production
    p = new_page(doc, FOREST)
    title_block(p, lang, c["production_kicker"], c["production_title"], light=True)
    production_images = [ASSETS / "make_oem.webp", ASSETS / "make_ingredient.webp", ASSETS / "make_supply.webp"]
    for i, ((label, body), image_path) in enumerate(zip(c["production"], production_images)):
        y = 190 + i * 185
        p.draw_rect(fitz.Rect(42, y, 553, y + 125), radius=0.06, color=None, fill=GREEN)
        add_image_cover(p, fitz.Rect(42, y, 226, y + 125), image_path)
        add_html(p, fitz.Rect(252, y + 22, 526, y + 105), f'<p class="card-title white">{html.escape(label)}</p><p class="card-body soft" style="font-size:9pt; margin-top:9pt">{html.escape(body)}</p>', lang, scale_low=0.72)
    add_footer(p, 6, total, lang, light=True)

    # 7. Portfolio overview
    p = new_page(doc)
    title_block(p, lang, c["portfolio_kicker"], c["portfolio_title"], c["portfolio_subtitle"])
    portfolio_rtl = LANGUAGES[lang]["dir"] == "rtl"
    for i, ((name, pack), image_path) in enumerate(zip(c["products"], PRODUCT_IMAGES.values())):
        row, col = divmod(i, 2)
        x = 42 + col * 261
        y = 200 + row * 132
        p.draw_rect(fitz.Rect(x, y, x + 240, y + 112), radius=0.06, color=None, fill=WHITE)
        if portfolio_rtl:
            image_rect = fitz.Rect(x + 134, y + 7, x + 232, y + 105)
            text_rect = fitz.Rect(x + 15, y + 24, x + 120, y + 94)
        else:
            image_rect = fitz.Rect(x + 8, y + 7, x + 106, y + 105)
            text_rect = fitz.Rect(x + 120, y + 24, x + 225, y + 94)
        add_image_fit(p, image_rect, image_path)
        add_html(p, text_rect, f'<p class="card-title" style="font-size:12pt">{html.escape(name)}</p><p class="label" style="margin-top:9pt">{html.escape(pack)}</p>', lang, scale_low=0.72)
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
        y = 220 + row * 118
        for col, (name, pack) in enumerate(pair):
            x = 42 + col * 261
            p.draw_rect(fitz.Rect(x, y, x + 240, y + 90), radius=0.05, color=None, fill=WHITE)
            add_html(p, fitz.Rect(x + 20, y + 17, x + 220, y + 76), f'<p class="card-title" style="font-size:13.5pt">{html.escape(name)}</p><p class="label" style="margin-top:7pt">{html.escape(pack)}</p>', lang, scale_low=0.72)
    p.draw_rect(fitz.Rect(42, 690, 553, 732), radius=0.04, color=None, fill=CREAM_2)
    add_html(p, fitz.Rect(58, 700, 537, 726), f'<p class="small" style="text-align:center">{html.escape(labels["pack_note"])}</p>', lang, scale_low=0.72)
    add_footer(p, 8, total, lang)

    # 9. Sales channels
    p = new_page(doc, FOREST)
    kicker, title, body = detail["channels"]
    title_block(p, lang, kicker, title, body, light=True)
    channels_rtl = LANGUAGES[lang]["dir"] == "rtl"
    for i, (label, copy) in enumerate(detail["channel_items"]):
        y = 220 + i * 126
        p.draw_rect(fitz.Rect(42, y, 553, y + 106), radius=0.06, color=None, fill=GREEN)
        if channels_rtl:
            number_rect = fitz.Rect(485, y + 28, 530, y + 78)
            title_rect = fitz.Rect(300, y + 24, 465, y + 82)
            copy_rect = fitz.Rect(65, y + 24, 285, y + 82)
        else:
            number_rect = fitz.Rect(62, y + 28, 102, y + 78)
            title_rect = fitz.Rect(118, y + 24, 295, y + 82)
            copy_rect = fitz.Rect(310, y + 24, 530, y + 82)
        add_html(p, number_rect, f'<p class="kicker">0{i + 1}</p>', lang)
        add_html(p, title_rect, f'<p class="card-title white" style="font-size:13pt">{html.escape(label)}</p>', lang, scale_low=0.72)
        add_html(p, copy_rect, f'<p class="card-body soft" style="font-size:9.3pt">{html.escape(copy)}</p>', lang, scale_low=0.72)
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
        history_cards = []
        for year, items in spread:
            list_items = []
            for item_index, item in enumerate(items):
                item_text = html.escape(item)
                if item_index == 0:
                    item_text = f'<b style="color:#ffffff">{item_text}</b>'
                list_items.append(
                    f'<li style="font-size:10pt;line-height:1.45;margin-bottom:5pt">{item_text}</li>'
                )
            list_markup = f'<ul style="color:#dce2dc;margin-top:0;padding-inline-start:16pt">{"".join(list_items)}</ul>'
            measured_height = measure_html_height(list_markup, lang, 367)
            card_height = max(128.0, measured_height + 44.0)
            history_cards.append((year, list_markup, card_height))
        history_gap = 16.0
        history_group_height = sum(card[2] for card in history_cards) + history_gap
        history_band = 568.0
        if history_group_height > history_band:
            raise RuntimeError(f"History cards overflow for {lang} page {10 + spread_index}: {history_group_height}")
        history_y = 190 + (history_band - history_group_height) / 2
        history_rtl = LANGUAGES[lang]["dir"] == "rtl"
        for year, list_markup, card_height in history_cards:
            card_bottom = history_y + card_height
            p.draw_rect(fitz.Rect(42, history_y, 553, card_bottom), radius=0.06, color=None, fill=GREEN)
            if history_rtl:
                year_rect = fitz.Rect(455, history_y + 22, 533, history_y + 78)
                list_rect = fitz.Rect(62, history_y + 22, 435, card_bottom - 18)
            else:
                year_rect = fitz.Rect(62, history_y + 22, 140, history_y + 78)
                list_rect = fitz.Rect(158, history_y + 22, 531, card_bottom - 18)
            add_html(p, year_rect, f'<p class="metric" style="font-size:24pt">{html.escape(year)}</p>', lang, scale_low=1)
            add_html(p, list_rect, list_markup, lang, scale_low=1)
            history_y = card_bottom + history_gap
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
    add_image_cover(p, fitz.Rect(42, 205, 235, 530), ASSETS / "team_walk.webp")
    add_html(p, fitz.Rect(266, 240, 530, 505), f'<p class="card-title">01 · {html.escape(labels["review"])}</p><p class="card-body" style="font-size:10pt;margin-top:9pt">{html.escape(c["partner_points"][0][1])}</p><p class="card-title" style="margin-top:22pt">02 · {html.escape(labels["consult"])}</p><p class="card-body" style="font-size:10pt;margin-top:9pt">{html.escape(detail["consultation"])}</p>', lang, scale_low=0.68)
    for i, (label, body) in enumerate(c["partner_points"]):
        x = 42 + i * 171
        p.draw_rect(fitz.Rect(x, 560, x + 154, 690), radius=0.06, color=None, fill=WHITE)
        add_html(p, fitz.Rect(x + 16, 578, x + 138, 674), f'<p class="kicker">0{i + 1}</p><p class="card-title" style="font-size:13pt;margin-top:9pt">{html.escape(label)}</p><p class="card-body" style="font-size:8.7pt;margin-top:11pt">{html.escape(body)}</p>', lang, scale_low=0.68)
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


def company_brochure_v5(lang: str) -> fitz.Document:
    """Build the homepage-led landscape company deck introduced in v5."""
    c = COMPANY_CONTENT[lang]
    detail = COMPANY_DETAIL[lang]
    labels = COMPANY_PAGE_LABELS[lang]
    home = HOMEPAGE_COMPANY[lang]
    rtl = LANGUAGES[lang]["dir"] == "rtl"
    doc = fitz.open()
    total = 14

    # 1. Cover — a presentation cover, not a portrait report template.
    p = new_company_page(doc, FOREST)
    add_image_cover(p, fitz.Rect(390, 0, 842, 595), ASSETS / "hero-dog-companion.webp")
    p.draw_rect(fitz.Rect(370, 0, 500, 595), color=None, fill=FOREST, fill_opacity=0.58, overlay=True)
    p.draw_rect(fitz.Rect(0, 0, 11, 595), color=None, fill=GOLD)
    add_logo(p, "company", fitz.Rect(48, 38, 112, 104))
    add_html(p, fitz.Rect(117, 58, 132, 84), '<p class="gold" style="font-size:12pt;font-weight:700;text-align:center">×</p>', lang)
    add_logo(p, "zero", fitz.Rect(138, 45, 252, 98))
    cover_markup = (
        f'<p class="kicker gold">{html.escape(c["cover_badge"])}</p>'
        f'<p class="white" style="font-size:37pt;line-height:1.12;font-weight:700;margin-top:15pt">'
        f'{html.escape(c["cover_title"]).replace(chr(10), "<br>")}</p>'
        f'<p class="soft" style="font-size:11pt;line-height:1.5;margin-top:18pt">{html.escape(c["cover_subtitle"])}</p>'
    )
    add_html(p, fitz.Rect(48, 158, 382, 420), cover_markup, lang, scale_low=0.8)
    add_html(p, fitz.Rect(48, 518, 360, 548), '<p class="small soft">COMPANION ANIMAL BUSINESS · INCHEON, KOREA</p>', lang, scale_low=1)
    company_footer(p, 1, total, lang, light=True)

    # 2. CEO message — homepage portrait and message, without a tall empty card.
    p = new_company_page(doc)
    ceo_kicker, ceo_title, ceo_quote, ceo_name, ceo_role = home["ceo"]
    company_title(p, lang, c["overview_kicker"], c["overview_title"], c["overview_body"], x=48, y=34, width=746, height=105)
    p.draw_rect(fitz.Rect(48, 156, 794, 516), radius=0.035, color=(0.88, 0.84, 0.74), fill=WHITE, width=0.6)
    add_image_cover(p, fitz.Rect(74, 182, 350, 490), ASSETS / "ceo_jangseonghwan.webp")
    add_html(p, fitz.Rect(392, 190, 758, 225), f'<p class="kicker">{html.escape(ceo_kicker)}</p>', lang, scale_low=1)
    add_html(p, fitz.Rect(392, 236, 758, 290), f'<p style="font-size:19pt;line-height:1.25;font-weight:700">{html.escape(ceo_title)}</p>', lang, scale_low=0.86)
    p.draw_line(fitz.Point(392, 315), fitz.Point(758, 315), color=GOLD, width=1.5)
    add_html(p, fitz.Rect(392, 334, 758, 414), f'<p style="font-size:10.2pt;line-height:1.65;font-weight:700;color:#1f3325">“{html.escape(ceo_quote)}”</p>', lang, scale_low=0.82)
    add_html(p, fitz.Rect(392, 444, 758, 490), f'<p style="font-size:11pt;font-weight:700">{html.escape(ceo_name)}</p><p style="font-size:8pt;color:#506056;margin-top:5pt">{html.escape(ceo_role)}</p>', lang, scale_low=0.88)
    company_footer(p, 2, total, lang)

    # 3. Team culture — homepage team photograph and both team-tee visuals.
    p = new_company_page(doc)
    team_kicker, team_title, team_body = home["team"]
    company_title(p, lang, team_kicker, team_title, team_body, x=48, y=34, width=746, height=102)
    p.draw_rect(fitz.Rect(48, 150, 794, 518), radius=0.035, color=(0.88, 0.84, 0.74), fill=WHITE, width=0.6)
    add_image_cover(p, fitz.Rect(72, 174, 356, 494), ASSETS / "team_walk.webp")
    tee_cards = [(ASSETS / "tee_black.webp", "TEAM TEE · BLACK"), (ASSETS / "tee_white.webp", "TEAM TEE · WHITE")]
    for i, (image_path, caption) in enumerate(tee_cards):
        x = 392 + i * 184
        p.draw_rect(fitz.Rect(x, 238, x + 166, 454), radius=0.025, color=(0.88, 0.84, 0.74), fill=CREAM, width=0.5)
        add_image_fit(p, fitz.Rect(x + 8, 248, x + 158, 402), image_path)
        add_html(p, fitz.Rect(x + 12, 417, x + 154, 445), f'<p class="label" style="font-size:7.5pt">{caption}</p>', lang, scale_low=1)
    company_footer(p, 3, total, lang)

    # 4. Company profile — compact label:value cards mirrored from the homepage.
    p = new_company_page(doc)
    profile_kicker, profile_title, profile_body, profile_items = home["profile"]
    company_title(p, lang, profile_kicker, profile_title, profile_body, x=48, y=34, width=746, height=102)
    profile_codes = ["BRAND", "COMPANY", "BUSINESS", "CHANNELS", "REG. NO.", "ADDRESS"]
    for i, (label, value, subvalue) in enumerate(profile_items):
        row, col = divmod(i, 3)
        visual_col = 2 - col if rtl else col
        x = 48 + visual_col * 249
        y = 158 + row * 168
        p.draw_rect(fitz.Rect(x, y, x + 229, y + 145), radius=0.035, color=(0.88, 0.84, 0.74), fill=WHITE, width=0.6)
        main_size = 9.5 if label in {"주소", "Address", "地址", "住所", "ที่อยู่", "العنوان"} else 13.5
        add_html(p, fitz.Rect(x + 20, y + 23, x + 209, y + 55), f'<p class="label" style="font-size:8pt">{profile_codes[i]}</p>', lang, scale_low=1)
        # MuPDF reverses this neutral numeric segment in an RTL paragraph.
        display_value = "03624-88-266" if lang == "ar" and profile_codes[i] == "REG. NO." else value
        value_markup = f'<bdo dir="ltr">{html.escape(display_value)}</bdo>'
        add_html(p, fitz.Rect(x + 20, y + 61, x + 209, y + 105), f'<p style="font-size:{main_size}pt;line-height:1.35;font-weight:700">{html.escape(label)} : {value_markup}</p>', lang, scale_low=0.78)
        add_html(p, fitz.Rect(x + 20, y + 112, x + 209, y + 137), f'<p style="font-size:7.7pt;color:#506056">{html.escape(subvalue)}</p>', lang, scale_low=0.8)
    company_footer(p, 4, total, lang)

    # 5. Made in Korea — actual production imagery and a connected process.
    p = new_company_page(doc)
    company_title(p, lang, c["production_kicker"], c["production_title"], x=48, y=36, width=746, height=86)
    production_images = [ASSETS / "make_oem.webp", ASSETS / "make_ingredient.webp", ASSETS / "make_supply.webp"]
    production_order = list(enumerate(zip(c["production"], production_images), start=1))
    if rtl:
        production_order.reverse()
    for visual_index, (semantic_index, ((label, body), image_path)) in enumerate(production_order):
        x = 48 + visual_index * 249
        add_image_cover(p, fitz.Rect(x, 142, x + 229, 370), image_path)
        p.draw_rect(fitz.Rect(x, 352, x + 229, 500), color=None, fill=FOREST)
        add_html(
            p,
            fitz.Rect(x + 14, 360, x + 215, 498),
            f'<p class="gold" style="font-size:7.5pt;font-weight:700">0{semantic_index}</p><p class="white" style="font-size:12pt;font-weight:700;margin-top:6pt">{html.escape(label)}</p><p class="soft" style="font-size:7.8pt;line-height:1.38;margin-top:7pt">{html.escape(body)}</p>',
            lang,
            scale_low=0.76,
        )
    add_html(p, fitz.Rect(48, 516, 794, 544), f'<p style="font-size:8pt;text-align:center;color:#657268">{html.escape(COMPANY_A_UI[lang]["process"])}</p>', lang, scale_low=1)
    company_footer(p, 5, total, lang)

    # 6. Product portfolio — products dominate the slide.
    p = new_company_page(doc, FOREST)
    company_title(p, lang, c["portfolio_kicker"], c["portfolio_title"], c["portfolio_subtitle"], light=True, x=48, y=34, width=746, height=96)
    company_product_images = [
        PRODUCT_IMAGES["meat"],
        PRODUCT_IMAGES["nutrition"],
        PRODUCT_IMAGES["berry"],
        PRODUCT_IMAGES["dental"],
        PRODUCT_IMAGES["baked"],
        PRODUCT_IMAGES["meatless"],
        PRODUCT_IMAGES["mungs"],
        PRODUCT_IMAGES["fresh"],
    ]
    products = list(zip(c["products"], company_product_images))
    if rtl:
        products = [products[i] for i in (3, 2, 1, 0, 7, 6, 5, 4)]
    for i, ((name, pack), image_path) in enumerate(products):
        row, col = divmod(i, 4)
        x = 48 + col * 187
        y = 150 + row * 188
        p.draw_rect(fitz.Rect(x, y, x + 169, y + 118), radius=0.035, color=None, fill=CREAM)
        add_image_fit(p, fitz.Rect(x + 7, y + 5, x + 162, y + 113), image_path)
        add_html(
            p,
            fitz.Rect(x, y + 130, x + 169, y + 177),
            f'<p class="white" style="font-size:10.5pt;font-weight:700">{html.escape(name)}</p><p class="gold" style="font-size:7.5pt;font-weight:700;margin-top:4pt">{html.escape(pack)}</p>',
            lang,
            scale_low=0.86,
        )
    company_footer(p, 6, total, lang, light=True)

    # 7. Brand principles — the three homepage principles in compact photo panels.
    p = new_company_page(doc)
    company_title(p, lang, c["principles_kicker"], c["principles_title"], x=48, y=34, width=746, height=84)
    principle_images = [ASSETS / "approach_remove.webp", ASSETS / "approach_balance.webp", ASSETS / "hero-dog-treats.webp"]
    principles = list(enumerate(zip(c["principles"], principle_images), start=1))
    if rtl:
        principles.reverse()
    for visual_index, (semantic_index, ((label, body), image_path)) in enumerate(principles):
        x = 48 + visual_index * 249
        add_image_cover(p, fitz.Rect(x, 138, x + 229, 338), image_path)
        p.draw_rect(fitz.Rect(x, 338, x + 229, 474), color=None, fill=FOREST)
        add_html(p, fitz.Rect(x + 18, 356, x + 61, 389), f'<p class="gold" style="font-size:18pt;font-weight:700">0{semantic_index}</p>', lang, scale_low=1)
        add_html(p, fitz.Rect(x + 72, 353, x + 211, 389), f'<p class="white" style="font-size:14pt;font-weight:700">{html.escape(label)}</p>', lang, scale_low=0.86)
        add_html(p, fitz.Rect(x + 18, 404, x + 211, 462), f'<p class="soft" style="font-size:8.4pt;line-height:1.45">{html.escape(body)}</p>', lang, scale_low=0.8)
    company_footer(p, 7, total, lang)

    # 8. Routes to market — homepage channel facts without another tall process card.
    p = new_company_page(doc, FOREST)
    kicker, title, body = detail["channels"]
    company_title(p, lang, kicker, title, body, light=True, x=48, y=34, width=746, height=100)
    add_image_cover(p, fitz.Rect(48, 154, 392, 506), ASSETS / "hero-dog-treats.webp")
    p.draw_rect(fitz.Rect(48, 452, 392, 506), color=None, fill=FOREST, fill_opacity=0.64, overlay=True)
    add_html(p, fitz.Rect(70, 468, 370, 495), f'<p class="small soft" style="font-size:7.5pt;text-align:center">{html.escape(COMPANY_A_UI[lang]["routes"])}</p>', lang, scale_low=1)
    channels = list(zip(detail["channel_items"], CHANNEL_URLS))
    for i, ((label, copy), uri) in enumerate(channels):
        y = 158 + i * 87
        p.draw_line(fitz.Point(430, y), fitz.Point(794, y), color=MID_GREEN, width=0.8)
        add_html(p, fitz.Rect(430, y + 18, 471, y + 50), f'<p class="kicker">0{i + 1}</p>', lang, scale_low=1)
        add_html(p, fitz.Rect(482, y + 13, 620, y + 49), f'<p class="white" style="font-size:11pt;font-weight:700">{html.escape(label)}</p>', lang, scale_low=0.86)
        add_html(p, fitz.Rect(630, y + 12, 794, y + 58), f'<p class="soft" style="font-size:8pt;line-height:1.4">{html.escape(copy)}</p>', lang, scale_low=0.82)
        p.insert_link({"kind": fitz.LINK_URI, "from": fitz.Rect(426, y + 4, 794, y + 72), "uri": uri})
    company_footer(p, 8, total, lang, light=True)

    # 9-11. Milestones — editorial timelines, not giant empty cards.
    history = c["history"]
    for spread_index in range(3):
        p = new_company_page(doc, FOREST)
        spread = history[spread_index * 2 : spread_index * 2 + 2]
        years = f'{spread[-1][0]}–{spread[0][0]}' if rtl else f'{spread[0][0]}–{spread[-1][0]}'
        years_markup = f'<bdo dir="ltr">{html.escape(years)}</bdo>' if rtl else html.escape(years)
        history_markup = f'<p class="kicker">{html.escape(c["history_kicker"])}</p><p class="white" style="font-size:25pt;line-height:1.13;font-weight:700;margin-top:7pt">{html.escape(c["history_title"])} · {years_markup}</p><p style="font-size:9.5pt;line-height:1.45;color:#dce2dc;margin-top:8pt">{html.escape(c["history_subtitle"])}</p>'
        add_html(p, fitz.Rect(48, 30, 794, 135), history_markup, lang, scale_low=0.9)
        columns = [48, 438]
        if rtl:
            columns.reverse()
        for x, (year, items) in zip(columns, spread):
            add_html(p, fitz.Rect(x, 158, x + 342, 207), f'<p class="gold" style="font-size:30pt;font-weight:700">{html.escape(year)}</p>', lang, scale_low=1)
            p.draw_line(fitz.Point(x, 216), fitz.Point(x + 342, 216), color=GOLD, width=1.2)
            item_markup = []
            for item_index, item in enumerate(items):
                weight = "font-weight:700;color:#ffffff;" if item_index == 0 else "color:#dce2dc;"
                if rtl:
                    item_markup.append(f'<p style="font-size:8.4pt;line-height:1.4;margin:0 0 3.5pt;{weight}text-align:right">{html.escape(item)}&nbsp;<span style="color:#d8b36a">•</span></p>')
                else:
                    item_markup.append(f'<li style="font-size:8.4pt;line-height:1.4;margin-bottom:3.5pt;{weight}">{html.escape(item)}</li>')
            history_list = "".join(item_markup) if rtl else f'<ul style="margin:0;padding-inline-start:15pt">{"".join(item_markup)}</ul>'
            add_html(
                p,
                fitz.Rect(x, 238, x + 342, 510),
                history_list,
                lang,
                scale_low=0.86,
            )
        add_html(p, fitz.Rect(48, 526, 794, 548), f'<p class="small soft" style="font-size:7pt;text-align:center">{html.escape(labels["history_note"])}</p>', lang, scale_low=0.88)
        company_footer(p, 9 + spread_index, total, lang, light=True)

    # 12. Donation campaign — the complete homepage story, not a generic metric list.
    p = new_company_page(doc)
    donation_kicker, donation_title, donation_body, donation_caption, donation_items = home["donation"]
    company_title(p, lang, donation_kicker, donation_title, donation_body, x=48, y=34, width=746, height=105)
    p.draw_rect(fitz.Rect(48, 158, 360, 500), radius=0.035, color=None, fill=FOREST)
    add_image_cover(p, fitz.Rect(48, 158, 360, 330), ASSETS / "hero-dog-companion.webp")
    p.draw_rect(fitz.Rect(48, 274, 360, 330), color=None, fill=FOREST, fill_opacity=0.55, overlay=True)
    add_html(p, fitz.Rect(72, 362, 336, 414), f'<p class="gold" style="font-size:29pt;font-weight:700">{html.escape(DONATION_AMOUNT_LABELS[lang])}</p>', lang, scale_low=0.88)
    add_html(p, fitz.Rect(72, 424, 336, 478), f'<p class="soft" style="font-size:8.7pt;line-height:1.5;font-weight:700">{html.escape(donation_caption)}</p>', lang, scale_low=0.84)
    for i, (label, body) in enumerate(donation_items):
        y = 174 + i * 158
        p.draw_line(fitz.Point(402, y), fitz.Point(794, y), color=(0.78, 0.79, 0.73), width=0.8)
        add_html(p, fitz.Rect(402, y + 24, 456, y + 55), f'<p class="kicker">0{i + 1}</p>', lang, scale_low=1)
        add_html(p, fitz.Rect(474, y + 20, 776, y + 56), f'<p style="font-size:15pt;font-weight:700">{html.escape(label)}</p>', lang, scale_low=0.84)
        add_html(p, fitz.Rect(474, y + 72, 776, y + 130), f'<p style="font-size:9pt;line-height:1.55;color:#506056">{html.escape(body)}</p>', lang, scale_low=0.8)
    company_footer(p, 12, total, lang)

    # 13. Partnership — the repeat-sales proposition after the team story.
    p = new_company_page(doc)
    # Let the contact image meet the forest panel directly.  The former
    # translucent bridge band rendered as an unintended black vertical stripe
    # in PDF viewers, especially at the image boundary.
    add_image_cover(p, fitz.Rect(470, 0, 842, 595), ASSETS / "hero-dog-treats.webp")
    company_title(p, lang, c["partner_kicker"], c["partner_title"], c["partner_body"], x=48, y=42, width=418, height=118, title_size=22)
    for i, (label, body) in enumerate(c["partner_points"]):
        y = 196 + i * 96
        p.draw_line(fitz.Point(48, y), fitz.Point(458, y), color=(0.78, 0.79, 0.73), width=0.8)
        add_html(p, fitz.Rect(48, y + 17, 88, y + 50), f'<p class="kicker">0{i + 1}</p>', lang, scale_low=1)
        add_html(p, fitz.Rect(104, y + 13, 214, y + 59), f'<p style="font-size:12pt;font-weight:700">{html.escape(label)}</p>', lang, scale_low=0.84)
        add_html(p, fitz.Rect(226, y + 10, 470, y + 73), f'<p style="font-size:8.4pt;line-height:1.5;color:#506056">{html.escape(body)}</p>', lang, scale_low=0.8)
    add_html(p, fitz.Rect(48, 492, 458, 540), f'<p style="font-size:8.5pt;line-height:1.5;color:#1f3325;font-weight:700">{html.escape(detail["consultation"])}</p>', lang, scale_low=0.86)
    company_footer(p, 13, total, lang)

    # 14. Contact — a clean commercial hand-off with live links.
    p = new_company_page(doc, FOREST)
    add_image_cover(p, fitz.Rect(470, 0, 842, 595), ASSETS / "hero-dog-treats.webp")
    add_logo(p, "company", fitz.Rect(48, 34, 112, 100))
    add_html(p, fitz.Rect(117, 54, 132, 80), '<p class="gold" style="font-size:12pt;font-weight:700;text-align:center">×</p>', lang)
    add_logo(p, "zero", fitz.Rect(138, 41, 252, 94))
    company_title(p, lang, c["contact_kicker"], c["contact_title"], c["contact_subtitle"], light=True, x=48, y=130, width=370, height=112)
    contact_pairs = list(zip(c["contact_labels"], CONTACT_VALUES, CONTACT_URIS))
    for i, (label, value, uri) in enumerate(contact_pairs[:5]):
        y = 268 + i * 43
        add_html(p, fitz.Rect(48, y, 156, y + 30), f'<p class="label" style="font-size:7.2pt">{html.escape(label)}</p>', lang, scale_low=1)
        add_html(p, fitz.Rect(166, y - 1, 430, y + 31), f'<p class="white" style="font-size:8.4pt;font-weight:700">{html.escape(value)}</p>', lang, scale_low=0.86)
        if uri:
            p.insert_link({"kind": fitz.LINK_URI, "from": fitz.Rect(160, y - 2, 430, y + 32), "uri": uri})
    q1 = qr_png("https://companimal.kr", "qr-company.png")
    q2 = qr_png("https://pf.kakao.com/_xnyDcs", "qr-kakao.png")
    for x, image_path, uri in ((48, q1, "https://companimal.kr"), (138, q2, "https://pf.kakao.com/_xnyDcs")):
        p.draw_rect(fitz.Rect(x, 478, x + 70, 548), radius=0.025, color=None, fill=WHITE)
        add_image_fit(p, fitz.Rect(x + 5, 483, x + 65, 543), image_path)
        p.insert_link({"kind": fitz.LINK_URI, "from": fitz.Rect(x, 478, x + 70, 548), "uri": uri})
    add_html(p, fitz.Rect(230, 481, 430, 538), f'<p class="small soft" style="font-size:7pt;line-height:1.5">{html.escape(c["disclosure"])}</p>', lang, scale_low=0.86)
    company_footer(p, 14, total, lang, light=True)

    doc.set_metadata({"title": c["title"], "author": "Companimal Co., Ltd.", "subject": "Company profile v5", "keywords": f"Companimal, ZERO LABS, {LANGUAGES[lang]['locale']}"})
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


PRODUCT_A_IMAGE_KEYS = {
    "meat_1kg": "meat",
    "meat_350g": "meat",
    "nutrition_1kg": "nutrition",
    "nutrition_350g": "nutrition",
    "berry_1kg": "berry",
    "berry_400g": "berry",
    "dental": "dental",
    "baked_1kg": "baked",
    "baked_200g": "baked",
    "meatless": "meatless",
    "fresh_ring": "fresh",
    "mungs": "mungs",
}

PRODUCT_A_UI = {
    "ko": {"buyer": "바이어용 비교", "title": "제품 · 포장 · 구성", "body": "사진을 줄이는 대신 비교 가능한 정렬과 밀도를 우선합니다.", "product": "제품", "pack": "포장", "range": "구성", "b2b": "MOQ · 공급가 · 리드타임", "counts": {"1": "1종", "3": "3종", "4": "4종"}},
    "en": {"buyer": "BUYER VIEW", "title": "Product · Pack · Range", "body": "A compact comparison view for product and trade review.", "product": "Product", "pack": "Pack", "range": "Range", "b2b": "MOQ · wholesale price · lead time", "counts": {"1": "1 variety", "3": "3 varieties", "4": "4 varieties"}},
    "zh-hans": {"buyer": "采购对照", "title": "产品 · 包装 · 组合", "body": "以可比较的排列和信息密度为优先。", "product": "产品", "pack": "包装", "range": "组合", "b2b": "起订量 · 供货价 · 交期", "counts": {"1": "1种", "3": "3种", "4": "4种"}},
    "zh-hant": {"buyer": "採購對照", "title": "產品 · 包裝 · 組合", "body": "以可比較的排列與資訊密度為優先。", "product": "產品", "pack": "包裝", "range": "組合", "b2b": "起訂量 · 供貨價 · 交期", "counts": {"1": "1種", "3": "3種", "4": "4種"}},
    "ja": {"buyer": "バイヤー向け比較", "title": "商品 · 容量 · 構成", "body": "比較しやすい整列と情報密度を優先します。", "product": "商品", "pack": "容量", "range": "構成", "b2b": "MOQ · 卸価格 · リードタイム", "counts": {"1": "1種", "3": "3種", "4": "4種"}},
    "th": {"buyer": "มุมมองสำหรับผู้ซื้อ", "title": "สินค้า · ขนาด · ชุด", "body": "จัดเรียงข้อมูลให้เปรียบเทียบสินค้าและการค้าได้ง่าย", "product": "สินค้า", "pack": "ขนาด", "range": "ชุด", "b2b": "MOQ · ราคาขายส่ง · ระยะเวลา", "counts": {"1": "1 แบบ", "3": "3 แบบ", "4": "4 แบบ"}},
    "ar": {"buyer": "مقارنة للمشترين", "title": "المنتج · العبوة · المجموعة", "body": "ترتيب موجز يسهل مقارنة المنتجات وشروط التجارة.", "product": "المنتج", "pack": "العبوة", "range": "المجموعة", "b2b": "الحد الأدنى · سعر الجملة · مدة التوريد", "counts": {"1": "نوع واحد", "3": "3 أنواع", "4": "4 أنواع"}},
}


def product_a_footer(page: fitz.Page, page_no: int, total: int, lang: str, *, light: bool = False) -> None:
    color = "#dce2dc" if light else "#657268"
    add_html(page, fitz.Rect(48, 558, 720, 579), f'<p style="font-size:7.2pt;color:{color}">ZERO LABS · {html.escape(PRODUCT_CONTENT[lang]["title"])} · 2026</p>', lang, scale_low=1)
    add_html(page, fitz.Rect(742, 558, 794, 579), f'<p style="font-size:7.2pt;color:{color};text-align:right">{page_no:02d} / {total:02d}</p>', lang, scale_low=1)


def product_a_heading(page: fitz.Page, lang: str, kicker: str, title: str, body: str = "", *, light: bool = False, rect: fitz.Rect = fitz.Rect(48, 34, 794, 126), size: float = 25) -> None:
    title_color = "#ffffff" if light else "#16241a"
    body_color = "#dce2dc" if light else "#506056"
    markup = f'<p class="kicker" style="color:{"#d8b36a" if light else "#a57d30"}">{html.escape(kicker)}</p><p style="font-size:{size}pt;line-height:1.15;font-weight:700;color:{title_color};margin-top:8pt">{html.escape(title)}</p>'
    if body:
        markup += f'<p style="font-size:9pt;line-height:1.45;color:{body_color};margin-top:9pt">{html.escape(body)}</p>'
    add_html(page, rect, markup, lang, scale_low=0.82)


def product_a_card(page: fitz.Page, lang: str, item: tuple[str, str, list[str], str], image_key: str, rect: fitz.Rect, *, dark: bool = False) -> None:
    name, description, bullets, pack = item
    fill = GREEN if dark else WHITE
    title_color = "#ffffff" if dark else "#16241a"
    body_color = "#dce2dc" if dark else "#506056"
    page.draw_rect(rect, radius=0.025, color=(0.88, 0.84, 0.74), fill=fill, width=0.5)
    compact = rect.height < 250
    image_bottom = rect.y0 + (120 if compact else 142)
    text_top = rect.y0 + (130 if compact else 154)
    add_image_fit(page, fitz.Rect(rect.x0 + 10, rect.y0 + 10, rect.x1 - 10, image_bottom), PRODUCT_IMAGES[image_key])
    if rect.height < 250:
        markup = f'<p style="font-size:10pt;font-weight:700;color:{title_color}">{html.escape(name)}</p><p style="font-size:7.5pt;font-weight:700;color:{"#d8b36a" if dark else "#a57d30"};margin-top:4pt">{html.escape(pack)}</p>'
    else:
        markup = f'<p style="font-size:13pt;font-weight:700;color:{title_color}">{html.escape(name)}</p><p style="font-size:8pt;line-height:1.4;color:{body_color};margin-top:6pt">{html.escape(description)}</p><p style="font-size:8.5pt;font-weight:700;color:{"#d8b36a" if dark else "#a57d30"};margin-top:8pt">{html.escape(pack)}</p>'
    add_html(page, fitz.Rect(rect.x0 + 14, text_top, rect.x1 - 14, rect.y1 - 12), markup, lang, scale_low=0.78)


def product_a_detail(page: fitz.Page, lang: str, item: tuple[str, str, list[str], str], image_key: str, *, page_no: int, rtl: bool = False, accent: str = GOLD) -> None:
    name, description, bullets, pack = item
    page.draw_rect(fitz.Rect(0, 0, 842, 595), color=None, fill=FOREST)
    image_panel = fitz.Rect(394, 34, 806, 530) if rtl else fitz.Rect(36, 34, 448, 530)
    image_rect = fitz.Rect(image_panel.x0 + 16, 50, image_panel.x1 - 16, 500)
    text_x0, text_x1 = (52, 352) if rtl else (490, 790)
    page.draw_rect(image_panel, color=None, fill=CREAM)
    add_image_fit(page, image_rect, PRODUCT_IMAGES[image_key])
    add_html(page, fitz.Rect(text_x0, 50, text_x1, 80), '<p class="kicker" style="color:#d8b36a">PRODUCT DETAIL</p>', lang, scale_low=1)
    add_html(page, fitz.Rect(text_x0, 92, text_x1, 175), f'<p style="font-size:28pt;line-height:1.12;font-weight:700;color:#ffffff">{html.escape(name)}</p><p style="font-size:9pt;line-height:1.45;color:#dce2dc;margin-top:10pt">{html.escape(description)}</p>', lang, scale_low=0.82)
    for index, bullet in enumerate(bullets):
        y = 226 + index * 66
        page.draw_line(fitz.Point(text_x0, y), fitz.Point(text_x1, y), color=MID_GREEN, width=0.8)
        add_html(page, fitz.Rect(text_x0, y + 16, text_x0 + 40, y + 46), f'<p style="font-size:8pt;color:#d8b36a;font-weight:700">0{index + 1}</p>', lang, scale_low=1)
        add_html(page, fitz.Rect(text_x0 + 54, y + 12, text_x1, y + 51), f'<p style="font-size:10pt;color:#ffffff;font-weight:700">{html.escape(bullet)}</p>', lang, scale_low=0.82)
    add_html(page, fitz.Rect(text_x0, 436, text_x1, 500), f'<p style="font-size:23pt;color:#d8b36a;font-weight:700">{html.escape(pack)}</p>', lang, scale_low=0.86)
    product_a_footer(page, page_no, 16, lang, light=True)


def product_brochure_a(lang: str) -> fitz.Document:
    """Build the selected green, product-first visual catalogue in 16 landscape pages."""
    c = PRODUCT_CONTENT[lang]
    rtl = LANGUAGES[lang]["dir"] == "rtl"
    doc = fitz.open()
    total = 16

    # 1. Cover
    p = new_company_page(doc, FOREST)
    add_image_cover(p, fitz.Rect(438, 0, 842, 595), ASSETS / "hero-dog-treats.webp")
    p.draw_rect(fitz.Rect(390, 0, 515, 595), color=None, fill=FOREST, fill_opacity=0.70, overlay=True)
    add_logo(p, "zero", fitz.Rect(50, 40, 186, 102))
    product_a_heading(p, lang, c["cover_version"], c["cover_tagline"], c["greeting"][0], light=True, rect=fitz.Rect(50, 155, 400, 380), size=32)
    product_a_footer(p, 1, total, lang, light=True)

    # 2. Editorial introduction
    p = new_company_page(doc)
    product_a_heading(p, lang, c["greeting_title"], c["greeting_title"], c["greeting"][0], rect=fitz.Rect(48, 36, 794, 135), size=25)
    add_image_cover(p, fitz.Rect(48, 158, 365, 510), ASSETS / "hero-dog-treats.webp")
    p.draw_rect(fitz.Rect(390, 158, 794, 510), radius=0.03, color=(0.88, 0.84, 0.74), fill=WHITE, width=0.6)
    body = "".join(f'<p style="font-size:10pt;line-height:1.7;color:#506056;margin-bottom:17pt">{html.escape(paragraph)}</p>' for paragraph in c["greeting"])
    add_html(p, fitz.Rect(420, 190, 760, 450), f'<p style="font-size:17pt;font-weight:700">{html.escape(c["title"])}</p>{body}', lang, scale_low=0.82)
    product_a_footer(p, 2, total, lang)

    # 3. Line-up overview
    p = new_company_page(doc)
    product_a_heading(p, lang, "PRODUCT LINEUP", c["catalog_title"], " · ".join(c["catalog"][:8]), rect=fitz.Rect(48, 34, 794, 118), size=25)
    lineups = [("meat_1kg", "meat"), ("nutrition_1kg", "nutrition"), ("berry_1kg", "berry"), ("dental", "dental"), ("baked_1kg", "baked"), ("meatless", "meatless"), ("mungs", "mungs"), ("fresh_ring", "fresh")]
    for index, (key, image_key) in enumerate(lineups):
        row, col = divmod(index, 4)
        visual_col = 3 - col if rtl else col
        x, y = 48 + visual_col * 187, 140 + row * 188
        item = c["products"][key]
        product_a_card(p, lang, item, image_key, fitz.Rect(x, y, x + 169, y + 173))
    product_a_footer(p, 3, total, lang)

    # 4. Category map
    p = new_company_page(doc, FOREST)
    product_a_heading(p, lang, "PRODUCT FAMILIES", c["catalog_title"], " · ".join(c["catalog"][:4]), light=True, rect=fitz.Rect(48, 34, 794, 118), size=25)
    families = [("meat_1kg", "meat"), ("dental", "dental"), ("baked_1kg", "baked")]
    for index, (key, image_key) in enumerate(families):
        visual_index = 2 - index if rtl else index
        x = 48 + visual_index * 249
        item = c["products"][key]
        product_a_card(p, lang, item, image_key, fitz.Rect(x, 150, x + 229, 488), dark=True)
    product_a_footer(p, 4, total, lang, light=True)

    # 5–12. Individual product stories and pack variants.
    detail_pages = [
        ("meat_1kg", "meat"), ("meat_350g", "meat"),
        ("nutrition_1kg", "nutrition"), ("nutrition_350g", "nutrition"),
        ("berry_1kg", "berry"), ("berry_400g", "berry"),
        ("dental", "dental"), ("baked_1kg", "baked"),
    ]
    for page_no, (key, image_key) in enumerate(detail_pages, start=5):
        product_a_detail(new_company_page(doc, FOREST), lang, c["products"][key], image_key, page_no=page_no, rtl=rtl)

    # 13. Remaining product families.
    p = new_company_page(doc, FOREST)
    product_a_heading(p, lang, "MORE TO EXPLORE", c["catalog_title"], " · ".join(c["catalog"][4:8]), light=True, rect=fitz.Rect(48, 34, 794, 118), size=25)
    remaining = [("baked_200g", "baked"), ("meatless", "meatless"), ("fresh_ring", "fresh"), ("mungs", "mungs")]
    for index, (key, image_key) in enumerate(remaining):
        row, col = divmod(index, 4)
        visual_col = 3 - col if rtl else col
        x = 48 + visual_col * 187
        product_a_card(p, lang, c["products"][key], image_key, fitz.Rect(x, 150, x + 169, 480), dark=True)
    product_a_footer(p, 13, total, lang, light=True)

    # 14. Trial packs
    p = new_company_page(doc)
    product_a_heading(p, lang, c["trial_title"], c["trial_title"], c["trial_intro"], rect=fitz.Rect(48, 34, 794, 118), size=25)
    trial = [("meat_350g", "meat"), ("nutrition_350g", "nutrition"), ("berry_400g", "berry"), ("baked_200g", "baked")]
    for index, (key, image_key) in enumerate(trial):
        x = 48 + index * 150
        item = c["products"][key]
        p.draw_rect(fitz.Rect(x, 150, x + 132, 382), radius=0.025, color=(0.88, 0.84, 0.74), fill=WHITE, width=0.5)
        add_image_fit(p, fitz.Rect(x + 8, 160, x + 124, 307), PRODUCT_IMAGES[image_key])
        add_html(p, fitz.Rect(x + 8, 322, x + 124, 365), f'<p style="font-size:8.5pt;font-weight:700;text-align:center">{html.escape(item[0])}</p><p style="font-size:8pt;color:#a57d30;text-align:center;margin-top:4pt">30 g</p>', lang, scale_low=0.8)
    p.draw_rect(fitz.Rect(668, 150, 794, 382), radius=0.025, color=None, fill=FOREST)
    add_html(p, fitz.Rect(684, 178, 778, 360), f'<p class="kicker" style="color:#d8b36a">B2B</p><p style="font-size:14pt;color:#ffffff;font-weight:700;margin-top:8pt">{html.escape(c["contact_title"])}</p><p style="font-size:8pt;line-height:1.5;color:#dce2dc;margin-top:14pt">{html.escape(PRODUCT_A_UI[lang]["b2b"])}</p>', lang, scale_low=0.8)
    product_a_footer(p, 14, total, lang)

    # 15. Buyer comparison
    p = new_company_page(doc, CREAM)
    ui = PRODUCT_A_UI[lang]
    product_a_heading(p, lang, ui["buyer"], ui["title"], ui["body"], rect=fitz.Rect(48, 34, 794, 118), size=25)
    rows = ["meat_1kg", "meat_350g", "nutrition_1kg", "nutrition_350g", "berry_1kg", "berry_400g", "dental", "baked_1kg", "baked_200g", "meatless", "fresh_ring", "mungs"]
    headers = [ui["product"], ui["pack"], ui["range"]]
    for x, header in zip((190, 460, 665), headers):
        add_html(p, fitz.Rect(x, 135, x + 120, 162), f'<p class="label" style="font-size:7.5pt">{header}</p>', lang, scale_low=1)
    for index, key in enumerate(rows):
        y = 166 + index * 29
        item = c["products"][key]
        p.draw_line(fitz.Point(48, y), fitz.Point(794, y), color=(0.82, 0.80, 0.74), width=0.5)
        add_image_fit(p, fitz.Rect(52, y + 3, 132, y + 25), PRODUCT_IMAGES[PRODUCT_A_IMAGE_KEYS[key]])
        count = "3" if "3" in item[3] else "4" if "4" in item[3] else "1"
        values = (item[0], item[3], ui["counts"][count])
        for x, value in zip((190, 460, 665), values):
            add_html(p, fitz.Rect(x, y + 6, x + 135, y + 24), f'<p style="font-size:7.3pt;font-weight:700">{html.escape(value)}</p>', lang, scale_low=0.78)
    product_a_footer(p, 15, total, lang)

    # 16. Contact
    p = new_company_page(doc, FOREST)
    image_rect = fitz.Rect(0, 0, 372, 595) if rtl else fitz.Rect(470, 0, 842, 595)
    add_image_cover(p, image_rect, ASSETS / "hero-dog-treats.webp")
    add_logo(p, "zero", fitz.Rect(604, 40, 740, 102) if rtl else fitz.Rect(48, 40, 186, 102))
    text_rect = fitz.Rect(402, 142, 794, 255) if rtl else fitz.Rect(48, 142, 440, 255)
    product_a_heading(p, lang, "CONTACT", c["contact_title"], c["contact_intro"], light=True, rect=text_rect, size=27)
    profile_items = HOMEPAGE_COMPANY[lang]["profile"][3]
    contact_values = ["companimal.kr", "pf.kakao.com", "bldh2025@naver.com", profile_items[-1][1]]
    for index, (label, value) in enumerate(zip(c["contact_labels"], contact_values)):
        y = 286 + index * 50
        x0, x1 = (402, 560) if rtl else (48, 170)
        vx0, vx1 = (574, 794) if rtl else (182, 448)
        add_html(p, fitz.Rect(x0, y, x1, y + 28), f'<p class="label" style="font-size:7.5pt;color:#d8b36a">{html.escape(label)}</p>', lang, scale_low=1)
        add_html(p, fitz.Rect(vx0, y - 2, vx1, y + 30), f'<p style="font-size:9pt;color:#ffffff;font-weight:700">{html.escape(value)}</p>', lang, scale_low=0.82)
    q1 = qr_png("https://companimal.kr", "qr-company.png")
    q2 = qr_png("https://pf.kakao.com/_xnyDcs", "qr-kakao.png")
    qr_xs = (696, 604) if rtl else (48, 140)
    for x, image_path, uri in zip(qr_xs, (q1, q2), ("https://companimal.kr", "https://pf.kakao.com/_xnyDcs")):
        p.draw_rect(fitz.Rect(x, 484, x + 70, 554), color=None, fill=WHITE)
        add_image_fit(p, fitz.Rect(x + 5, 489, x + 65, 549), image_path)
        p.insert_link({"kind": fitz.LINK_URI, "from": fitz.Rect(x, 484, x + 70, 554), "uri": uri})
    disclosure_rect = fitz.Rect(402, 488, 794, 548) if rtl else fitz.Rect(235, 488, 445, 548)
    add_html(p, disclosure_rect, f'<p class="small soft" style="font-size:7pt;line-height:1.5">{html.escape(c["contact_disclosure"])}</p>', lang, scale_low=0.82)
    product_a_footer(p, 16, total, lang, light=True)

    doc.set_metadata({"title": c["title"], "author": "Companimal Co., Ltd.", "subject": "ZERO LABS product brochure — visual catalogue A", "keywords": f"ZERO LABS, dog treats, {LANGUAGES[lang]['locale']}"})
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
    row_height = max((image.height for image in thumbs), default=310) + 10
    sheet = Image.new("RGB", (columns * 230, rows * row_height), "white")
    for i, image in enumerate(thumbs):
        x = (i % columns) * 230 + 5
        y = (i // columns) * row_height + 5
        sheet.paste(image, (x, y))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, quality=92)


def build(languages: list[str]) -> dict[str, dict[str, object]]:
    prepare_font_files()
    ensure_inputs()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    results: dict[str, dict[str, object]] = {}
    for lang in languages:
        company_path = OUTPUT / f"company-profile-{lang}-2026-v6.pdf"
        product_path = OUTPUT / f"product-brochure-{lang}-2026-v3.pdf"
        save_with_language(company_brochure_v5(lang), company_path, LANGUAGES[lang]["locale"])
        save_with_language(product_brochure_a(lang), product_path, LANGUAGES[lang]["locale"])
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
    if set(results) == set(LANGUAGES):
        manifest = OUTPUT / "brochure-files.json"
        staged_manifest = OUTPUT / "brochure-files.json.new"
        staged_manifest.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(staged_manifest, manifest)
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--languages", nargs="+", default=list(LANGUAGES), choices=list(LANGUAGES))
    args = parser.parse_args()
    print(json.dumps(build(args.languages), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

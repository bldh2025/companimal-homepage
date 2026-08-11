/**
 * 방문 통계. 동의를 받기 전에는 어떤 측정 스크립트도 불러오지 않는다.
 *
 * 아래 두 ID를 채우면 동작한다. 비어 있으면 배너도 뜨지 않고 아무것도 로드하지 않으므로,
 * ID 발급 전에 배포해도 사이트에는 영향이 없다.
 */
(function () {
  "use strict";

  var GA4_ID = "";     // 예: "G-XXXXXXXXXX" — Google Analytics 4 측정 ID
  var NAVER_ID = "";   // 예: "1a2b3c4d5e"   — 네이버 애널리틱스 인증 ID

  if (!GA4_ID && !NAVER_ID) return;

  var STORAGE_KEY = "companimal-analytics-consent";

  var COPY = {
    ko: {
      message: "방문 통계를 위해 쿠키를 사용합니다. 어떤 소개서가 도움이 되는지 파악해 사이트를 개선하는 데만 씁니다.",
      accept: "동의",
      decline: "거부",
      label: "쿠키 사용 동의"
    },
    en: {
      message: "We use cookies to measure visits. They only help us see which brochures are useful and improve the site.",
      accept: "Accept",
      decline: "Decline",
      label: "Cookie consent"
    },
    "zh-hans": {
      message: "我们使用 Cookie 统计访问情况，仅用于了解哪些资料更有帮助并改进网站。",
      accept: "同意",
      decline: "拒绝",
      label: "Cookie 使用同意"
    },
    "zh-hant": {
      message: "我們使用 Cookie 統計造訪情況，僅用於了解哪些資料更有幫助並改善網站。",
      accept: "同意",
      decline: "拒絕",
      label: "Cookie 使用同意"
    }
  };

  function pageLanguage() {
    var lang = (document.documentElement.lang || "ko").toLowerCase();
    if (lang.indexOf("zh-hant") === 0 || lang.indexOf("zh-tw") === 0) return "zh-hant";
    if (lang.indexOf("zh") === 0) return "zh-hans";
    if (lang.indexOf("en") === 0) return "en";
    return "ko";
  }

  function storedConsent() {
    try {
      return window.localStorage.getItem(STORAGE_KEY);
    } catch (error) {
      // 시크릿 모드 등에서 localStorage 가 막히면 매번 다시 묻는다.
      return null;
    }
  }

  function rememberConsent(value) {
    try {
      window.localStorage.setItem(STORAGE_KEY, value);
    } catch (error) {
      /* 저장하지 못해도 이번 방문에는 선택이 적용된다. */
    }
  }

  function loadScript(src, onload) {
    var tag = document.createElement("script");
    tag.async = true;
    tag.src = src;
    if (onload) tag.onload = onload;
    document.head.appendChild(tag);
  }

  var track = function () {}; // 동의 전에는 이벤트를 버린다.

  function startAnalytics() {
    if (GA4_ID) {
      window.dataLayer = window.dataLayer || [];
      var gtag = function () { window.dataLayer.push(arguments); };
      window.gtag = gtag;
      gtag("js", new Date());
      gtag("config", GA4_ID, { page_language: pageLanguage() });
      loadScript("https://www.googletagmanager.com/gtag/js?id=" + encodeURIComponent(GA4_ID));
      track = function (name, params) {
        gtag("event", name, params);
      };
    }
    if (NAVER_ID) {
      loadScript("https://wcs.naver.net/wcslog.js", function () {
        if (!window.wcs) return;
        window.wcs_add = window.wcs_add || {};
        window.wcs_add.wa = NAVER_ID;
        if (window.wcs_do) window.wcs_do();
      });
    }
  }

  function showBanner() {
    var copy = COPY[pageLanguage()];
    var banner = document.createElement("aside");
    banner.className = "consent";
    banner.setAttribute("role", "region");
    banner.setAttribute("aria-label", copy.label);

    var text = document.createElement("p");
    text.textContent = copy.message;

    var actions = document.createElement("div");
    actions.className = "consent-actions";

    function button(className, label, value) {
      var el = document.createElement("button");
      el.type = "button";
      el.className = className;
      el.textContent = label;
      el.addEventListener("click", function () {
        rememberConsent(value);
        banner.classList.remove("show");
        window.setTimeout(function () { banner.remove(); }, 300);
        if (value === "granted") startAnalytics();
      });
      return el;
    }

    actions.appendChild(button("accept", copy.accept, "granted"));
    actions.appendChild(button("decline", copy.decline, "denied"));
    banner.appendChild(text);
    banner.appendChild(actions);
    document.body.appendChild(banner);
    // 트랜지션이 걸리도록 한 프레임 뒤에 올린다.
    window.requestAnimationFrame(function () { banner.classList.add("show"); });
  }

  var CHANNELS = [
    ["zerolabs.co.kr", "official_mall"],
    ["coupang.com", "coupang"],
    ["xn--yj2b7mx8w6tf.com", "b2b_wholesale"],
    ["smartstore.naver.com", "smartstore"]
  ];

  function placementOf(link) {
    if (link.closest("header")) return "header";
    if (link.closest("footer")) return "footer";
    if (link.closest(".hero")) return "hero";
    if (link.classList.contains("kakao-float")) return "floating";
    return "body";
  }

  function bindEvents() {
    document.addEventListener("click", function (event) {
      var link = event.target.closest("a");
      if (!link) return;
      var language = pageLanguage();

      var card = link.closest("[data-brochure-kind]");
      if (card && link.hasAttribute("data-download-link")) {
        var select = card.querySelector("select");
        track("brochure_download", {
          brochure: card.getAttribute("data-brochure-kind"),
          brochure_language: select ? select.value : "ko",
          page_language: language
        });
        return;
      }

      var href = link.getAttribute("href") || "";
      if (href.indexOf("mailto:") === 0) {
        track("contact_click", { method: "email", placement: placementOf(link), page_language: language });
        return;
      }
      if (href.indexOf("pf.kakao.com") !== -1) {
        track("contact_click", { method: "kakao", placement: placementOf(link), page_language: language });
        return;
      }
      if (href === "#contact") {
        track("b2b_inquiry_click", { placement: placementOf(link), page_language: language });
        return;
      }
      for (var i = 0; i < CHANNELS.length; i++) {
        if (href.indexOf(CHANNELS[i][0]) !== -1) {
          track("channel_click", { channel: CHANNELS[i][1], page_language: language });
          return;
        }
      }
    });
  }

  bindEvents();

  var consent = storedConsent();
  if (consent === "granted") startAnalytics();
  else if (consent !== "denied") showBanner();
})();

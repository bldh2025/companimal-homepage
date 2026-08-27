(function () {
  "use strict";

  function element(doc, tag, text, style) {
    var node = doc.createElement(tag);
    if (text !== undefined && text !== null) node.textContent = text;
    if (style) node.setAttribute("style", style);
    return node;
  }

  function pad(number) {
    return String(number).padStart(2, "0");
  }

  function productImages(lineup, snapshot, keys) {
    var images = Array.from(lineup.querySelectorAll("img"));
    return keys.map(function (key) {
      var label = snapshot.products[key] && snapshot.products[key].label;
      var matches = images.filter(function (image) {
        return label && (image.getAttribute("alt") || "").indexOf(label) !== -1;
      });
      if (matches.length !== 1) throw new Error("Company product image mapping is ambiguous: " + key);
      return matches[0];
    });
  }

  function replaceContactPlaceholders(doc) {
    var replacements = {
      "[ 이메일 입력 ]": "ceo@companimal.kr",
      "[ 도매몰 주소 입력 ]": "제로랩스.com"
    };
    var walker = doc.createTreeWalker(doc.body, NodeFilter.SHOW_TEXT);
    var node;
    while ((node = walker.nextNode())) {
      Object.keys(replacements).forEach(function (from) {
        if (node.nodeValue.indexOf(from) !== -1) {
          node.nodeValue = node.nodeValue.replaceAll(from, replacements[from]);
        }
      });
    }
  }

  function makeReviewSlide(doc, lineup, snapshot) {
    var keys = ["meat", "nutrition", "berry", "dental", "baked", "meatless", "mungs", "fresh"];
    var images = productImages(lineup, snapshot, keys);
    if (keys.reduce(function (sum, key) { return sum + snapshot.products[key].count; }, 0) !== snapshot.total) {
      throw new Error("Review snapshot total does not match its products");
    }

    var slide = element(doc, "section");
    slide.setAttribute("data-label", "07 리뷰 데이터");
    slide.setAttribute("data-screen-label", "07");
    slide.setAttribute("data-review-proof", "true");
    slide.setAttribute("data-review-as-of", snapshot.asOfIso);
    slide.setAttribute("data-speaker-notes", "판매채널 화면의 공개 리뷰 게시물 수를 제품군 단위로 합산한 기준일 스냅샷.");
    slide.setAttribute("style", "background:#1f3325;color:#f4f8f0;font-family:'IBM Plex Sans KR',sans-serif;padding:76px 88px;box-sizing:border-box;display:grid;grid-template-rows:auto 1fr auto;gap:34px;");

    var header = element(doc, "div", null, "display:flex;justify-content:space-between;align-items:flex-end;gap:56px;");
    var heading = element(doc, "div", null, "display:flex;flex-direction:column;gap:14px;");
    heading.appendChild(element(doc, "h2", "전체 판매채널 누적 리뷰 " + snapshot.total.toLocaleString("ko-KR") + "건", "margin:0;font-size:62px;font-weight:600;letter-spacing:-0.03em;line-height:1.14;"));
    heading.appendChild(element(doc, "p", "쿠팡을 포함한 회사 제공 판매채널의 공개 리뷰를 제품군 기준으로 합산했습니다. 다음 페이지에서 쿠팡 단일 채널 수치를 구분해 보여드립니다.", "margin:0;font-size:27px;line-height:1.55;font-weight:300;color:#c8d8cd;max-width:1280px;"));
    header.appendChild(heading);
    header.appendChild(element(doc, "span", "05 — MARKET PROOF", "font-size:24px;letter-spacing:0.18em;color:#a7d8b4;white-space:nowrap;flex:none;"));
    slide.appendChild(header);

    var content = element(doc, "div", null, "display:grid;grid-template-columns:0.34fr 0.66fr;gap:34px;min-height:0;");
    var total = element(doc, "div", null, "background:#a7d8b4;color:#12261a;padding:46px;display:flex;flex-direction:column;justify-content:space-between;min-width:0;");
    total.appendChild(element(doc, "span", "제품군 누적 리뷰 게시물", "font-size:24px;color:#2f5c3c;"));
    var totalValue = element(doc, "div", null, "display:flex;align-items:flex-end;gap:12px;flex-wrap:wrap;");
    totalValue.appendChild(element(doc, "strong", snapshot.total.toLocaleString("ko-KR"), "font-size:92px;line-height:0.95;letter-spacing:-0.055em;font-weight:650;"));
    totalValue.appendChild(element(doc, "span", "건", "font-size:34px;font-weight:600;padding-bottom:8px;"));
    total.appendChild(totalValue);
    var totalMeta = element(doc, "div", null, "display:grid;grid-template-columns:1fr 1fr;gap:18px;border-top:1px solid #7fba8f;padding-top:24px;");
    var families = element(doc, "div");
    families.appendChild(element(doc, "strong", "8개", "display:block;font-size:34px;"));
    families.appendChild(element(doc, "span", "집계 제품군", "font-size:21px;color:#2f5c3c;"));
    totalMeta.appendChild(families);
    var date = element(doc, "div");
    date.appendChild(element(doc, "strong", snapshot.asOf, "display:block;font-size:34px;"));
    date.appendChild(element(doc, "span", "기준일", "font-size:21px;color:#2f5c3c;"));
    totalMeta.appendChild(date);
    total.appendChild(totalMeta);
    content.appendChild(total);

    var grid = element(doc, "div", null, "display:grid;grid-template-columns:repeat(4,1fr);grid-template-rows:repeat(2,1fr);gap:16px;min-width:0;");
    keys.forEach(function (key, index) {
      var product = snapshot.products[key];
      var card = element(doc, "article", null, "background:#fbfcf9;color:#1f3325;padding:15px 16px 14px;display:grid;grid-template-rows:1fr auto auto;min-width:0;overflow:hidden;");
      var image = images[index].cloneNode(true);
      image.removeAttribute("width");
      image.removeAttribute("height");
      image.setAttribute("style", "display:block;width:100%;height:145px;object-fit:contain;min-height:0;");
      card.appendChild(image);
      card.appendChild(element(doc, "h3", product.label, "margin:7px 0 2px;font-size:25px;line-height:1.2;font-weight:600;"));
      card.appendChild(element(doc, "strong", product.count.toLocaleString("ko-KR") + "건", "font-size:29px;line-height:1.2;color:#3f6b4a;font-weight:650;"));
      grid.appendChild(card);
    });
    content.appendChild(grid);
    slide.appendChild(content);
    slide.appendChild(element(doc, "p", snapshot.definition, "margin:0;border-top:1px solid #33513b;padding-top:20px;font-size:20px;line-height:1.5;color:#9dbaa5;"));
    return slide;
  }

  function makeCoupangReviewSlide(doc, lineup, snapshot) {
    var keys = ["meat", "nutrition", "berry", "dental", "baked", "meatless", "mungs", "fresh"];
    var coupang = snapshot.coupang;
    if (!coupang || !coupang.products) throw new Error("Coupang review snapshot is unavailable");
    var images = productImages(lineup, snapshot, keys);
    if (keys.reduce(function (sum, key) { return sum + coupang.products[key].count; }, 0) !== coupang.total) {
      throw new Error("Coupang review snapshot total does not match its products");
    }
    keys.forEach(function (key) {
      if (!snapshot.products[key] || coupang.products[key].count > snapshot.products[key].count) {
        throw new Error("Coupang review count exceeds the all-channel count: " + key);
      }
    });

    var slide = element(doc, "section");
    slide.setAttribute("data-label", "08 쿠팡 리뷰");
    slide.setAttribute("data-screen-label", "08");
    slide.setAttribute("data-channel-review-proof", "coupang");
    slide.setAttribute("data-review-as-of", coupang.asOfIso);
    slide.setAttribute("data-speaker-notes", "쿠팡 상품 페이지의 공개 리뷰 게시물 수를 8개 제품군 단위로 합산한 기준일 스냅샷.");
    slide.setAttribute("style", "background:#f4efe5;color:#1f3325;font-family:'IBM Plex Sans KR',sans-serif;padding:76px 88px;box-sizing:border-box;display:grid;grid-template-rows:auto 1fr auto;gap:34px;");

    var header = element(doc, "div", null, "display:flex;justify-content:space-between;align-items:flex-end;gap:56px;");
    var heading = element(doc, "div", null, "display:flex;flex-direction:column;gap:14px;");
    heading.appendChild(element(doc, "h2", "쿠팡 누적 리뷰 " + coupang.total.toLocaleString("ko-KR") + "건", "margin:0;font-size:62px;font-weight:600;letter-spacing:-0.03em;line-height:1.14;"));
    heading.appendChild(element(doc, "p", "8개 제품군의 쿠팡 상품 페이지에 표시된 공개 리뷰 게시물 수를 합산했습니다.", "margin:0;font-size:27px;line-height:1.55;font-weight:300;color:#4c5c50;max-width:1280px;"));
    header.appendChild(heading);
    header.appendChild(element(doc, "span", "06 — COUPANG PROOF", "font-size:24px;letter-spacing:0.18em;color:#3f6b4a;white-space:nowrap;flex:none;"));
    slide.appendChild(header);

    var content = element(doc, "div", null, "display:grid;grid-template-columns:0.34fr 0.66fr;gap:34px;min-height:0;");
    var total = element(doc, "div", null, "background:#1f3325;color:#f4f8f0;padding:46px;display:flex;flex-direction:column;justify-content:space-between;min-width:0;");
    total.appendChild(element(doc, "span", "쿠팡 누적 리뷰 게시물", "font-size:24px;color:#a7d8b4;"));
    var totalValue = element(doc, "div", null, "display:flex;align-items:flex-end;gap:12px;flex-wrap:wrap;");
    totalValue.appendChild(element(doc, "strong", coupang.total.toLocaleString("ko-KR"), "font-size:92px;line-height:0.95;letter-spacing:-0.055em;font-weight:650;"));
    totalValue.appendChild(element(doc, "span", "건", "font-size:34px;font-weight:600;padding-bottom:8px;"));
    total.appendChild(totalValue);
    var totalMeta = element(doc, "div", null, "display:grid;grid-template-columns:1fr 1fr;gap:18px;border-top:1px solid #4b6853;padding-top:24px;");
    var families = element(doc, "div");
    families.appendChild(element(doc, "strong", "8개", "display:block;font-size:34px;"));
    families.appendChild(element(doc, "span", "집계 제품군", "font-size:21px;color:#a7d8b4;"));
    totalMeta.appendChild(families);
    var date = element(doc, "div");
    date.appendChild(element(doc, "strong", coupang.asOf, "display:block;font-size:34px;"));
    date.appendChild(element(doc, "span", "기준일", "font-size:21px;color:#a7d8b4;"));
    totalMeta.appendChild(date);
    total.appendChild(totalMeta);
    total.appendChild(element(doc, "p", "전체 판매채널 합계 " + snapshot.total.toLocaleString("ko-KR") + "건과 구분된 쿠팡 단일 채널 수치입니다.", "margin:0;font-size:20px;line-height:1.5;color:#c8d8cd;"));
    content.appendChild(total);

    var grid = element(doc, "div", null, "display:grid;grid-template-columns:repeat(4,1fr);grid-template-rows:repeat(2,1fr);gap:16px;min-width:0;");
    keys.forEach(function (key, index) {
      var product = coupang.products[key];
      var card = element(doc, "article", null, "background:#fbfcf9;color:#1f3325;padding:15px 16px 14px;display:grid;grid-template-rows:1fr auto auto;min-width:0;overflow:hidden;border:1px solid #ddd3c4;");
      var image = images[index].cloneNode(true);
      image.removeAttribute("width");
      image.removeAttribute("height");
      image.setAttribute("style", "display:block;width:100%;height:145px;object-fit:contain;min-height:0;");
      card.appendChild(image);
      card.appendChild(element(doc, "h3", product.label, "margin:7px 0 2px;font-size:25px;line-height:1.2;font-weight:600;"));
      card.appendChild(element(doc, "strong", product.count.toLocaleString("ko-KR") + "건", "font-size:29px;line-height:1.2;color:#3f6b4a;font-weight:650;"));
      grid.appendChild(card);
    });
    content.appendChild(grid);
    slide.appendChild(content);
    slide.appendChild(element(doc, "p", coupang.definition, "margin:0;border-top:1px solid #d4cbbb;padding-top:20px;font-size:20px;line-height:1.5;color:#5b6b5e;"));
    return slide;
  }

  function updateContents(doc, snapshot) {
    var contents = doc.querySelector('section[data-label^="02 "]');
    if (!contents) throw new Error("Company contents slide is missing");
    contents.setAttribute("data-speaker-notes", "12개 섹션.");
    var list = contents.children[1];
    var rows = Array.from(list.children).filter(function (child) { return child.tagName === "DIV"; });
    var guide = rows.find(function (row) { return row.textContent.indexOf("제품 선택") !== -1; });
    if (!guide) throw new Error("Company guide row is missing from contents");
    var reviewRow = guide.cloneNode(true);
    var reviewSpans = reviewRow.querySelectorAll("span");
    reviewSpans[0].textContent = "05";
    reviewSpans[1].textContent = "전체 판매채널 · 누적 리뷰 " + snapshot.total.toLocaleString("ko-KR") + "건";
    guide.before(reviewRow);
    var coupangRow = guide.cloneNode(true);
    var coupangSpans = coupangRow.querySelectorAll("span");
    coupangSpans[0].textContent = "06";
    coupangSpans[1].textContent = "쿠팡 채널 · 누적 리뷰 " + snapshot.coupang.total.toLocaleString("ko-KR") + "건";
    guide.before(coupangRow);

    rows = Array.from(list.children).filter(function (child) { return child.tagName === "DIV"; });
    rows.forEach(function (row, index) {
      var spans = row.querySelectorAll("span");
      if (spans[0]) spans[0].textContent = pad(index + 1);
      row.style.padding = "9px 0";
      if (spans[1]) spans[1].style.fontSize = "31px";
    });
  }

  function renumberSections(root) {
    var sections = Array.from(root.children).filter(function (child) { return child.tagName === "SECTION"; });
    sections.forEach(function (section, index) {
      var pageNumber = pad(index + 1);
      var label = section.getAttribute("data-label") || "";
      section.setAttribute("data-label", /^\d{2} /.test(label) ? pageNumber + label.slice(2) : pageNumber + " " + label);
      section.setAttribute("data-screen-label", pageNumber);
      if (index < 2) return;
      var eyebrow = Array.from(section.querySelectorAll("span")).find(function (span) {
        return /^\d{2} — /.test(span.textContent.trim());
      });
      if (eyebrow) eyebrow.textContent = pad(index - 1) + eyebrow.textContent.trim().slice(2);
    });
    return sections;
  }

  window.enhanceCompanyProfile = function (doc) {
    if (window.__FORCE_COMPANY_PROFILE_ENHANCER_FAILURE__) throw new Error("Forced company profile enhancer failure");
    replaceContactPlaceholders(doc);
    var existingReview = doc.querySelector('[data-review-proof="true"]');
    var existingCoupangReview = doc.querySelector('[data-channel-review-proof="coupang"]');
    if (existingReview || existingCoupangReview) {
      if (existingReview && existingCoupangReview) return;
      throw new Error("Company profile review enhancement is only partially present");
    }
    var snapshot = window.ZERO_LABS_REVIEW_SNAPSHOT;
    if (!snapshot || !snapshot.products || !snapshot.coupang || !snapshot.coupang.products) throw new Error("Review snapshot is unavailable");
    var root = doc.querySelector("x-import");
    if (!root) throw new Error("Company deck import root is missing");
    var lineup = Array.from(root.children).find(function (section) {
      return section.tagName === "SECTION" && /제품 라인업$/.test(section.getAttribute("data-label") || "");
    });
    if (!lineup) throw new Error("Company product lineup slide is missing");
    var guide = Array.from(root.children).find(function (section) {
      return section.tagName === "SECTION" && /제품 선택 가이드$/.test(section.getAttribute("data-label") || "");
    });
    if (!guide) throw new Error("Company product guide slide is missing");

    var reviewSlide = makeReviewSlide(doc, lineup, snapshot);
    var coupangSlide = makeCoupangReviewSlide(doc, lineup, snapshot);
    lineup.after(reviewSlide);
    reviewSlide.after(coupangSlide);
    updateContents(doc, snapshot);
    var sections = renumberSections(root);
    if (sections.length !== 14 || sections[5] !== lineup || sections[6] !== reviewSlide || sections[7] !== coupangSlide || sections[8] !== guide) {
      throw new Error("Company review slide order is invalid");
    }
  };
})();

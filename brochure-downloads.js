(function () {
  "use strict";

  var languageOrder = ["ko", "en", "zh-hans", "zh-hant", "ja", "th", "ar"];

  function pageLanguage() {
    var current = (document.documentElement.lang || "ko").toLowerCase();
    if (current.indexOf("zh-hant") === 0 || current.indexOf("zh-tw") === 0) return "zh-hant";
    if (current.indexOf("zh") === 0) return "zh-hans";
    if (current.indexOf("en") === 0) return "en";
    return "ko";
  }

  function formatBytes(bytes) {
    return (bytes / 1024 / 1024).toFixed(1) + " MB";
  }

  function formatPages(pages) {
    var code = pageLanguage();
    if (code === "ko") return pages + "쪽";
    if (code === "zh-hans") return pages + "页";
    if (code === "zh-hant") return pages + "頁";
    return pages + (pages === 1 ? " page" : " pages");
  }

  function enhanceCard(card, manifest) {
    var kind = card.getAttribute("data-brochure-kind");
    var select = card.querySelector("select");
    var link = card.querySelector("a[data-download-link]");
    var size = card.querySelector("[data-file-size]");
    if (!select || !link || !manifest.ko || !manifest.ko[kind]) return;

    select.replaceChildren();
    languageOrder.forEach(function (code) {
      var entry = manifest[code];
      if (!entry || !entry[kind]) return;
      var option = document.createElement("option");
      option.value = code;
      option.textContent = pageLanguage() === "ko" && entry.label_ko ? entry.label_ko : entry.label;
      option.lang = entry.locale;
      select.appendChild(option);
    });
    if (manifest[pageLanguage()]) select.value = pageLanguage();

    function updateDownload() {
      var code = select.value;
      var entry = manifest[code];
      var file = entry && entry[kind];
      if (code === "ko" && entry && entry[kind + "Html"]) file = entry[kind + "Html"];
      if (!file) return;
      link.href = "/" + file.path;
      if (file.format === "html") link.removeAttribute("download");
      else link.download = file.path.split("/").pop();
      link.hreflang = entry.locale;
      link.type = file.format === "html" ? "text/html" : "application/pdf";
      if (file.format === "html" && link.dataset.downloadLabelHtml) link.textContent = link.dataset.downloadLabelHtml;
      if (file.format !== "html" && link.dataset.downloadLabelPdf) link.textContent = link.dataset.downloadLabelPdf;
      if (size) size.textContent = (file.format === "html" ? "HTML · " : "PDF · ") + formatPages(file.pages) + " · " + formatBytes(file.bytes);
    }

    select.addEventListener("change", updateDownload);
    updateDownload();
  }

  fetch("/output/pdf/brochure-files.json", { credentials: "same-origin" })
    .then(function (response) {
      if (!response.ok) throw new Error("Brochure manifest unavailable");
      return response.json();
    })
    .then(function (manifest) {
      document.querySelectorAll("[data-brochure-kind]").forEach(function (card) {
        enhanceCard(card, manifest);
      });
    })
    .catch(function () {
      // The server-rendered Korean PDF links remain usable as a safe fallback.
    });
})();

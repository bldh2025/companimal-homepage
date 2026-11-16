(function () {
  "use strict";

  var context = document.querySelector(".inquiry-context");
  var selection = document.getElementById("inquiry-selection");
  var guide = document.getElementById("inquiry-guide");
  var email = document.querySelector("[data-inquiry-email]");

  document.querySelectorAll("[data-inquiry-label]").forEach(function (link) {
    link.addEventListener("click", function () {
      if (!context || !selection || !guide || !email) return;
      var label = link.getAttribute("data-inquiry-label");
      var instructions = link.getAttribute("data-inquiry-guide");
      context.hidden = false;
      selection.textContent = label;
      guide.textContent = instructions;
      email.href = "mailto:ceo@companimal.kr?subject=" + encodeURIComponent("ZERO LABS · " + label);
    });
  });

  // Existing bookmarks and the full-history link must reveal folded content.
  function revealAnchor(hash) {
    if (!hash || hash === "#") return;
    var id;
    try { id = decodeURIComponent(hash.slice(1)); } catch (_) { return; }
    var target = document.getElementById(id);
    if (!target) return;
    var parent = target.parentElement;
    var opened = false;
    while (parent) {
      if (parent.tagName === "DETAILS" && !parent.open) {
        parent.open = true;
        opened = true;
      }
      parent = parent.parentElement;
    }
    if (opened) window.requestAnimationFrame(function () { target.scrollIntoView(); });
  }

  document.addEventListener("click", function (event) {
    var link = event.target.closest("a[href^='#']");
    if (link) revealAnchor(link.getAttribute("href"));
  });
  window.addEventListener("hashchange", function () { revealAnchor(window.location.hash); });
  revealAnchor(window.location.hash);
})();

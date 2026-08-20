(function () {
  "use strict";
  var replacements = {
    "[ 이메일 입력 ]": "bldh2025@naver.com",
    "[ 도매몰 주소 입력 ]": "제로랩스.com"
  };
  function replaceText() {
    var walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    var node;
    while ((node = walker.nextNode())) {
      Object.keys(replacements).forEach(function (from) {
        if (node.nodeValue.indexOf(from) !== -1) node.nodeValue = node.nodeValue.replaceAll(from, replacements[from]);
      });
    }
  }
  replaceText();
  new MutationObserver(replaceText).observe(document.body, { childList: true, subtree: true });
})();

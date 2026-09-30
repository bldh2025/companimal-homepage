/* Embedded by localize_company_profiles.py after the Korean enhancer. */
(function () {
  'use strict';
  const config = __COMPANY_LOCALE_CONFIG__;
  window.localizeCompanyProfile = function (doc) {
    const walker = doc.createTreeWalker(doc.body, NodeFilter.SHOW_TEXT);
    let node;
    const missing = new Set();
    while ((node = walker.nextNode())) {
      if (node.parentElement.closest('script,style')) continue;
      const text = node.nodeValue.trim();
      if (!text || !/[가-힣]/.test(text) || text === '제로랩스.com') continue;
      let translated = config.mapping[text];
      if (!translated && /^[\d,]+건$/.test(text)) translated = text.slice(0, -1) + ' ' + config.reviewUnit;
      if (!translated) { missing.add(text); continue; }
      node.nodeValue = node.nodeValue.replace(text, translated);
      node.parentElement.dataset.localeText = 'true';
    }
    if (missing.size) throw new Error('Untranslated company copy: ' + Array.from(missing).join(' | '));
    const sections = Array.from(doc.querySelectorAll('section'));
    sections.forEach((section, i) => {
      section.setAttribute('data-label', config.labels[i]);
      section.setAttribute('data-screen-label', String(i + 1).padStart(2, '0'));
      section.removeAttribute('data-speaker-notes');
      section.dir = config.code === 'ar' ? 'rtl' : 'ltr';
      for (const el of section.querySelectorAll('[style]')) {
        // Translation expansion needs space in the fixed 1920 x 1080 layout.
        const size = parseFloat(el.style.fontSize);
        if (size >= 50) el.style.fontSize = Math.round(size * 0.83) + 'px';
        else if (size >= 20) el.style.fontSize = Math.round(size * 0.86) + 'px';
        if (config.code === 'ar') el.style.letterSpacing = '0';
      }
      for (const img of section.querySelectorAll('img')) {
        const alt = img.getAttribute('alt') || '';
        const key = Object.keys(config.mapping).sort((a,b) => b.length-a.length).find(k => alt.includes(k));
        if (/[가-힣]/.test(alt)) img.alt = key ? config.mapping[key] : 'ZERO LABS';
      }
      // Keep URLs, registration numbers and phone numbers in reading order.
      for (const el of section.querySelectorAll('span,strong,a')) {
        if (el.childElementCount === 0 && (/^(?:[\d,.-]+|.*@.*|[a-z]+\..*|제로랩스\.com)$/.test(el.textContent.trim()))) {
          el.dir = 'ltr'; el.style.unicodeBidi = 'isolate';
        }
      }
    });
    // Leave room for wrapped product names and the complete feeding strip.
    const guide = sections.find(section => section.getAttribute('data-screen-label') === '08');
    if (guide) {
      guide.style.gap = '24px';
      for (const row of guide.children[1].children) {
        row.style.padding = '12px 0';
        if (config.code === 'ja') row.children[2].style.width = '340px';
      }
      for (const cell of guide.children[2].querySelectorAll('span')) cell.style.fontSize = '20px';
    }
    const contact = sections.find(section => section.getAttribute('data-screen-label') === '13');
    if (contact) {
      contact.style.padding = '76px 96px'; contact.style.gap = '32px';
      for (const row of contact.children[1].children[0].children) {
        row.style.padding = '16px 0'; row.style.gap = '24px';
        row.children[0].style.flex = '0 0 190px';
        for (const span of row.children) { span.style.fontSize = '24px'; span.style.lineHeight = '1.45'; }
      }
      contact.lastElementChild.style.paddingTop = '24px';
    }
    if (config.code === 'ar') {
      // Isolate Latin names, addresses, units and numeric ranges inside RTL
      // sentences; otherwise a unit such as 215-26 can display as 26-215.
      for (const section of sections) {
        const texts = [];
        const rtlWalker = doc.createTreeWalker(section, NodeFilter.SHOW_TEXT);
        let textNode;
        while ((textNode = rtlWalker.nextNode())) texts.push(textNode);
        for (const textNode of texts) {
          const text = textNode.nodeValue;
          const parts = Array.from(text.matchAll(/[A-Za-z0-9][A-Za-z0-9 .,@()/_-]*[A-Za-z0-9.)]|[0-9]+/g));
          if (!parts.length) continue;
          const fragment = doc.createDocumentFragment();
          let offset = 0;
          for (const part of parts) {
            fragment.appendChild(doc.createTextNode(text.slice(offset, part.index)));
            const isolate = doc.createElement('bdi'); isolate.dir = 'ltr'; isolate.textContent = part[0];
            fragment.appendChild(isolate); offset = part.index + part[0].length;
          }
          fragment.appendChild(doc.createTextNode(text.slice(offset)));
          textNode.replaceWith(fragment);
        }
      }
    }
    doc.documentElement.lang = config.locale;
    doc.documentElement.dir = config.code === 'ar' ? 'rtl' : 'ltr';
    doc.documentElement.dataset.companyLocale = config.code;
    doc.title = config.title;
    const style = doc.createElement('style');
    style.textContent = __COMPANY_LOCALE_CSS__;
    doc.head.appendChild(style);
  };
})();

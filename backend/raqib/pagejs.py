"""In-page scripts shared by the scanner and the live browser agent."""

EXTRACT_JS = r"""() => {
  const vis = (el) => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const els = []; let n = 0;
  const add = (kind, o) => { if (els.length < 90) { n++; els.push(Object.assign({ id: 'e' + n, kind }, o || {})); } };
  const txt = (el, max) => (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, max || 220);
  const labelOf = (el) => {
    if (el.id) { const l = document.querySelector('label[for="' + CSS.escape(el.id) + '"]'); if (l) return txt(l, 60); }
    const p = el.closest('label'); if (p) return txt(p, 60);
    return el.getAttribute('aria-label') || el.placeholder || el.name || '';
  };
  const forms = [...document.forms].map((f, i) => ({ id: f.id || 'form' + i, action: f.getAttribute('action') ? f.action : '', method: (f.method || 'get').toLowerCase() }));
  const formId = (el) => { const f = el.form || el.closest('form'); return f ? (f.id || 'form' + [...document.forms].indexOf(f)) : ''; };
  const sel = 'header,h1,h2,h3,p,li,button,[role=button],a,input,select,textarea,footer,[class*=timer],[class*=countdown],[class*=alert],[class*=banner],[class*=warning]';
  for (const el of document.querySelectorAll(sel)) {
    if (!vis(el)) continue;
    const tag = el.tagName.toLowerCase(); const cls = (el.className && el.className.toString().toLowerCase()) || '';
    if (tag === 'input' || tag === 'textarea') {
      const type = (el.type || 'text').toLowerCase();
      if (['hidden', 'checkbox', 'radio'].includes(type)) continue;
      if (['submit', 'button'].includes(type)) { add('button', { text: el.value || 'Submit' }); continue; }
      add('input', { text: labelOf(el), form: formId(el), field: { name: el.name || '', type, autocomplete: el.autocomplete || '', placeholder: el.placeholder || '', label: labelOf(el), inputmode: el.inputMode || '', maxlength: el.maxLength > 0 ? el.maxLength : undefined } });
    } else if (tag === 'select') { add('select', { text: labelOf(el), form: formId(el), field: { name: el.name || '', type: 'select', autocomplete: el.autocomplete || '', label: labelOf(el) } }); }
    else if (tag === 'button' || el.getAttribute('role') === 'button') { add('button', { text: txt(el, 80) }); }
    else if (tag === 'a') {
      const href = el.getAttribute('href') || '';
      if (href.startsWith('tel:')) add('footer', { text: txt(el, 80), phone: href.slice(4) });
      else if (/wa\.me|whatsapp/i.test(href)) add('footer', { text: txt(el, 80), whatsapp: (href.match(/(\d{8,15})/) || [])[1] || '' });
      else if (href.startsWith('mailto:')) add('footer', { text: txt(el, 80), email: href.slice(7).split('?')[0] });
      else if (/btn|button|cta/.test(cls) && txt(el, 80)) add('button', { text: txt(el, 80) });
    }
    else if (/^h[1-3]$/.test(tag)) { add(el.closest('header') ? 'header' : 'heading', { text: txt(el, 160) }); }
    else if (tag === 'header') { const t = txt(el, 60); if (t) add('header', { text: t }); }
    else if (tag === 'footer') { const t = txt(el, 200); if (t) add('footer', { text: t }); }
    else if (/timer|countdown/.test(cls) || /^\d{1,2}:\d{2}(:\d{2})?$/.test(txt(el, 20))) { add('timer', { text: txt(el, 20) }); }
    else if (/alert|banner|warning/.test(cls)) { const t = txt(el, 200); if (t) add('banner', { text: t }); }
    else if (tag === 'p' || tag === 'li') { const t = txt(el, 240); if (t.length > 3) add('text', { text: t }); }
  }
  const scripts = [...document.scripts].map((s) => ({ src: s.src || '', inline: s.src ? '' : (s.textContent || '').slice(0, 30000) }));
  const icon = document.querySelector('link[rel~=icon]');
  const analytics = [...new Set((document.documentElement.innerHTML.match(/\b(?:G-[A-Z0-9]{8,12}|UA-\d{4,10}-\d{1,3}|GTM-[A-Z0-9]{6,8})\b/g) || []))];
  return { url: location.href, title: document.title, lang: document.documentElement.lang || '', elements: els, forms, scripts,
           favicon: icon ? icon.href : location.origin + '/favicon.ico', analytics, body: (document.body.innerText || '').slice(0, 20000), html: document.documentElement.outerHTML.slice(0, 200000) };
}"""

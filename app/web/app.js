/* CyberLibrarian – vanilla JS UI, zero external dependencies.
 *
 * Security contract:
 *  - All user-supplied or API-supplied text is set via textContent only.
 *  - URLs from the API are validated with safeUrl() before use.
 *  - No innerHTML assignments with dynamic data anywhere in this file.
 */

'use strict';

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
const STATE = {
  sessionId:   loadSessionId(),
  question:    '',
  response:    null,
  rating:      null,          // 'up' | 'down' | null
  feedbackDone: false,
  maxLen:      500,
};

function loadSessionId() {
  try {
    let id = localStorage.getItem('cl_session_id');
    if (!id) {
      id = crypto.randomUUID ? crypto.randomUUID().replace(/-/g, '') : randomHex(32);
      localStorage.setItem('cl_session_id', id);
    }
    return id;
  } catch { return randomHex(32); }
}

function randomHex(n) {
  const arr = new Uint8Array(n / 2);
  crypto.getRandomValues(arr);
  return Array.from(arr, b => b.toString(16).padStart(2, '0')).join('');
}

// ---------------------------------------------------------------------------
// DOM helpers (never use innerHTML for user data)
// ---------------------------------------------------------------------------
function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls)  e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

function safeUrl(url) {
  try {
    const u = new URL(url);
    return (u.protocol === 'http:' || u.protocol === 'https:') ? url : null;
  } catch { return null; }
}

function toast(msg, durationMs) {
  const container = document.getElementById('toast-container') ||
    (() => {
      const c = el('div', 'toast-container');
      c.id = 'toast-container';
      document.body.appendChild(c);
      return c;
    })();
  const t = el('div', 'toast', msg);
  container.appendChild(t);
  setTimeout(() => {
    t.classList.add('fade-out');
    t.addEventListener('animationend', () => t.remove(), { once: true });
  }, durationMs || 2500);
}

// ---------------------------------------------------------------------------
// Theme
// ---------------------------------------------------------------------------
(function initTheme() {
  try {
    const saved = localStorage.getItem('cl_theme');
    if (saved) document.documentElement.dataset.theme = saved;
  } catch {}

  const html = document.documentElement;
  const toggle = document.getElementById('theme-toggle');
  const sunIcon  = document.getElementById('icon-sun');
  const moonIcon = document.getElementById('icon-moon');

  function applyTheme(theme) {
    html.dataset.theme = theme;
    const isDark = theme === 'dark' ||
      (theme === 'auto' && window.matchMedia('(prefers-color-scheme: dark)').matches);
    if (sunIcon)  sunIcon.style.display  = isDark ? 'block' : 'none';
    if (moonIcon) moonIcon.style.display = isDark ? 'none'  : 'block';
    try { localStorage.setItem('cl_theme', theme); } catch {}
  }

  if (toggle) {
    toggle.addEventListener('click', () => {
      const current = html.dataset.theme || 'auto';
      const isDark = current === 'dark' ||
        (current === 'auto' && window.matchMedia('(prefers-color-scheme: dark)').matches);
      applyTheme(isDark ? 'light' : 'dark');
    });
  }

  const saved = (() => { try { return localStorage.getItem('cl_theme'); } catch { return null; } })();
  applyTheme(saved || 'auto');

  window.matchMedia('(prefers-color-scheme: dark)')
    .addEventListener('change', () => {
      if ((html.dataset.theme || 'auto') === 'auto') applyTheme('auto');
    });
})();

// ---------------------------------------------------------------------------
// Config load
// ---------------------------------------------------------------------------
async function loadConfig() {
  try {
    const r = await fetch('/api/config');
    if (!r.ok) return;
    const cfg = await r.json();
    STATE.maxLen = cfg.max_question_len || 500;

    // Update the textarea maxlength attribute to match server config
    const qi = document.getElementById('question-input');
    if (qi) qi.maxLength = STATE.maxLen;
    const cc = document.getElementById('char-count');
    if (cc) cc.textContent = '0 / ' + STATE.maxLen;

    // Mode pill
    const pill = document.getElementById('mode-pill');
    if (pill && cfg.mock_mode) {
      pill.textContent = 'MOCK';
      pill.style.display = 'inline-flex';
    } else if (pill) {
      pill.style.display = 'none';
    }

    // Example chips
    const chips = document.getElementById('example-chips');
    if (chips && Array.isArray(cfg.example_questions)) {
      cfg.example_questions.forEach(q => {
        const btn = el('button', 'chip');
        btn.setAttribute('role', 'listitem');
        btn.setAttribute('type', 'button');
        btn.setAttribute('aria-label', 'Ask: ' + q);
        // Show a truncated version in the chip but send the full question
        const preview = el('span');
        preview.textContent = q.length > 60 ? q.slice(0, 57) + '…' : q;
        btn.appendChild(preview);
        btn.addEventListener('click', () => fillAndSubmit(q));
        chips.appendChild(btn);
      });
    }

    // Set current year as default year-to max
    const yearTo = document.getElementById('year-to');
    if (yearTo) {
      const now = new Date().getFullYear();
      yearTo.max = now;
      yearTo.value = now;
    }
  } catch (e) {
    console.warn('Config load failed:', e);
  }
}

function fillAndSubmit(q) {
  const qi = document.getElementById('question-input');
  if (qi) {
    qi.value = q;
    qi.dispatchEvent(new Event('input'));
  }
  document.getElementById('ask-btn')?.click();
}

// ---------------------------------------------------------------------------
// Filters
// ---------------------------------------------------------------------------
function readFilters() {
  const sources = Array.from(
    document.querySelectorAll('input[name="source"]:checked')
  ).map(i => i.value);

  const yearFrom = parseInt(document.getElementById('year-from')?.value, 10);
  const yearTo   = parseInt(document.getElementById('year-to')?.value,   10);
  const defaultTo = new Date().getFullYear();

  const filters = {};
  if (sources.length)            filters.source   = sources;
  if (!isNaN(yearFrom) && yearFrom !== 2015) filters.year_min = yearFrom;
  if (!isNaN(yearTo)   && yearTo  !== defaultTo) filters.year_max = yearTo;

  return Object.keys(filters).length ? filters : null;
}

function renderActiveTags() {
  const container = document.getElementById('active-filters');
  const badge     = document.getElementById('active-filter-count');
  if (!container) return;

  while (container.firstChild) container.removeChild(container.firstChild);

  const tags = [];

  document.querySelectorAll('input[name="source"]:checked').forEach(cb => {
    tags.push({ label: cb.value.toUpperCase(), remove: () => { cb.checked = false; renderActiveTags(); } });
  });

  const yearFrom = parseInt(document.getElementById('year-from')?.value, 10);
  const yearTo   = parseInt(document.getElementById('year-to')?.value,   10);
  const defaultTo = new Date().getFullYear();
  if (!isNaN(yearFrom) && (!isNaN(yearTo)) && (yearFrom !== 2015 || yearTo !== defaultTo)) {
    tags.push({
      label: yearFrom + '–' + yearTo,
      remove: () => {
        const yf = document.getElementById('year-from');
        const yt = document.getElementById('year-to');
        if (yf) yf.value = 2015;
        if (yt) yt.value = defaultTo;
        renderActiveTags();
      },
    });
  }

  tags.forEach(({ label, remove }) => {
    const tag = el('span', 'filter-tag');
    tag.setAttribute('role', 'listitem');
    const lbl = el('span', null, label);
    const rmBtn = el('button', 'filter-tag-remove', '×');
    rmBtn.setAttribute('aria-label', 'Remove filter ' + label);
    rmBtn.addEventListener('click', remove);
    tag.appendChild(lbl);
    tag.appendChild(rmBtn);
    container.appendChild(tag);
  });

  if (badge) {
    if (tags.length > 0) {
      badge.textContent = tags.length;
      badge.hidden = false;
    } else {
      badge.hidden = true;
    }
  }
}

// ---------------------------------------------------------------------------
// Answer text renderer (safe: no innerHTML with dynamic data)
// ---------------------------------------------------------------------------
function renderAnswerText(text) {
  const container = el('div', 'answer-body');
  const paragraphs = text.split(/\n\n+/);
  paragraphs.forEach(para => {
    if (!para.trim()) return;
    const p = document.createElement('p');
    appendInlineNodes(p, para);
    container.appendChild(p);
  });
  return container;
}

function appendInlineNodes(parent, text) {
  // Tokenise: **bold**, `code`, [N] citation, plain text
  const pattern = /\*\*(.+?)\*\*|`([^`]+)`|\[(\d+)\]|([^`*[]+|\*(?!\*)|(?:\[(?!\d+\])))/g;
  let m;
  while ((m = pattern.exec(text)) !== null) {
    if (m[1] !== undefined) {
      const s = document.createElement('strong');
      s.textContent = m[1];
      parent.appendChild(s);
    } else if (m[2] !== undefined) {
      const c = document.createElement('code');
      c.textContent = m[2];
      parent.appendChild(c);
    } else if (m[3] !== undefined) {
      const n = parseInt(m[3], 10);
      const a = el('a', 'cite-chip', '[' + n + ']');
      a.href = '#source-' + n;
      a.setAttribute('aria-label', 'Citation ' + n);
      a.addEventListener('click', e => { e.preventDefault(); highlightSource(n); });
      parent.appendChild(a);
    } else if (m[4] !== undefined) {
      parent.appendChild(document.createTextNode(m[4]));
    }
  }
}

function highlightSource(n) {
  const card = document.getElementById('source-' + n);
  if (!card) return;
  // Open sources list if closed
  const list = document.getElementById('sources-list');
  if (list) list.hidden = false;
  const toggle = document.getElementById('sources-toggle');
  if (toggle) toggle.classList.add('open');
  card.classList.add('highlighted');
  card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  setTimeout(() => card.classList.remove('highlighted'), 2500);
}

// ---------------------------------------------------------------------------
// Render states
// ---------------------------------------------------------------------------
function showSkeleton() {
  const area = document.getElementById('answer-area');
  if (!area) return;
  while (area.firstChild) area.removeChild(area.firstChild);

  const card = el('div', 'skeleton-card');
  const prog = el('div', 'skeleton-progress');
  const h    = el('div', 'skeleton-line skeleton-header');

  card.appendChild(prog);
  card.appendChild(h);
  [90, 75, 82, 65, 70, 55].forEach(w => {
    const line = el('div', 'skeleton-line');
    line.style.width = w + '%';
    card.appendChild(line);
  });
  area.appendChild(card);
}

function showError(status, detail) {
  const area = document.getElementById('answer-area');
  if (!area) return;
  while (area.firstChild) area.removeChild(area.firstChild);

  let cls = 'state-card error-card';
  let title = 'Something went wrong';
  let hint  = 'Check that the server is running and try again.';

  if (status === 429) {
    cls   = 'state-card ratelimit-card';
    title = 'Rate limit reached';
    hint  = 'You\'ve sent too many questions this hour. Please wait a moment and try again.';
  } else if (status === 400) {
    title = 'Invalid question';
    hint  = 'Your question may be too long or empty. Please shorten it and try again.';
  } else if (status === 503) {
    title = 'Backend unavailable';
    hint  = 'The retrieval backend is not responding. Is the API server running?';
  }

  const card = el('div', cls);
  card.setAttribute('role', 'alert');
  card.appendChild(el('h3', null, title));
  card.appendChild(el('p',  null, hint));
  if (detail) {
    const d = el('div', 'error-detail');
    d.textContent = detail;
    card.appendChild(d);
  }
  area.appendChild(card);
}

function showAnswer(resp) {
  STATE.response   = resp;
  STATE.rating     = null;
  STATE.feedbackDone = false;

  const area = document.getElementById('answer-area');
  if (!area) return;
  while (area.firstChild) area.removeChild(area.firstChild);

  const card = el('div', 'answer-card');

  // Not-answerable banner
  if (!resp.answerable) {
    const banner = el('div', 'unknown-banner');
    const icon   = el('span', 'unknown-icon', '⚠');
    const body   = el('div');
    body.appendChild(el('strong', null, "I don't know based on the available documents."));
    body.appendChild(document.createElement('br'));
    body.appendChild(el('span', 'unknown-hint', 'The corpus may not cover this topic. Try rephrasing or broadening your question.'));
    banner.appendChild(icon);
    banner.appendChild(body);
    card.appendChild(banner);
  }

  // Answer text
  card.appendChild(renderAnswerText(resp.answer));

  // Meta line
  const meta = el('div', 'answer-meta');

  const latency = el('span', null, resp.latency_ms + ' ms');
  const s1 = el('span', 'meta-sep', '·');
  const tokens  = el('span', null, resp.tokens + ' tokens');
  const s2 = el('span', 'meta-sep', '·');
  const cost    = el('span', null, '$' + (resp.cost || 0).toFixed(4));
  meta.appendChild(latency);
  meta.appendChild(s1);
  meta.appendChild(tokens);
  meta.appendChild(s2);
  meta.appendChild(cost);

  if (resp.cache_hit) {
    const s3 = el('span', 'meta-sep', '·');
    const badge = el('span', 'cache-badge', 'CACHED');
    meta.appendChild(s3);
    meta.appendChild(badge);
  }

  // Copy-answer button
  const copyBtn = el('button', 'copy-btn', 'Copy');
  copyBtn.setAttribute('aria-label', 'Copy answer to clipboard');
  copyBtn.setAttribute('type', 'button');
  copyBtn.addEventListener('click', () => {
    navigator.clipboard.writeText(resp.answer).then(() => {
      copyBtn.textContent = 'Copied!';
      copyBtn.classList.add('copied');
      setTimeout(() => {
        copyBtn.textContent = 'Copy';
        copyBtn.classList.remove('copied');
      }, 2000);
    }).catch(() => toast('Could not copy to clipboard'));
  });
  meta.appendChild(copyBtn);

  card.appendChild(meta);

  // Sources
  if (resp.chunks && resp.chunks.length > 0) {
    card.appendChild(renderSources(resp.chunks, resp.citations || []));
  }

  // Feedback
  card.appendChild(renderFeedback(resp));

  area.appendChild(card);
}

// ---------------------------------------------------------------------------
// Sources panel
// ---------------------------------------------------------------------------
function renderSources(chunks, citations) {
  const section = el('div', 'sources-section');

  const toggleBtn = el('button', 'sources-toggle');
  toggleBtn.id = 'sources-toggle';
  toggleBtn.setAttribute('type', 'button');
  toggleBtn.setAttribute('aria-expanded', 'false');
  toggleBtn.setAttribute('aria-controls', 'sources-list');

  // Chevron SVG (safe static markup — not user data)
  const chevron = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  chevron.setAttribute('width', '14');
  chevron.setAttribute('height', '14');
  chevron.setAttribute('viewBox', '0 0 24 24');
  chevron.setAttribute('fill', 'none');
  chevron.setAttribute('stroke', 'currentColor');
  chevron.setAttribute('stroke-width', '2.5');
  chevron.setAttribute('stroke-linecap', 'round');
  chevron.setAttribute('stroke-linejoin', 'round');
  chevron.setAttribute('aria-hidden', 'true');
  const polyline = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
  polyline.setAttribute('points', '9 18 15 12 9 6');
  chevron.appendChild(polyline);

  toggleBtn.appendChild(chevron);
  toggleBtn.appendChild(document.createTextNode(' Sources (' + chunks.length + ')'));

  const list = el('div', 'sources-list');
  list.id = 'sources-list';
  list.hidden = true;

  toggleBtn.addEventListener('click', () => {
    const open = !list.hidden;
    list.hidden = open;
    toggleBtn.setAttribute('aria-expanded', String(!open));
    toggleBtn.classList.toggle('open', !open);
  });

  // Build a citation map: chunk_id → url
  const citationMap = {};
  (citations || []).forEach(c => { citationMap[c.chunk_id] = c.url; });

  chunks.forEach((result, idx) => {
    const chunk = result.chunk;
    const num   = idx + 1;
    const url   = safeUrl(citationMap[chunk.chunk_id] || '');

    const card = el('div', 'source-card');
    card.id = 'source-' + num;

    // Header row
    const header = el('div', 'source-card-header');
    const numBadge = el('span', 'source-num', String(num));
    const srcBadge = el('span', 'source-badge badge-' + chunk.source, chunk.source.toUpperCase());
    const scoreEl  = el('span', 'score-badge', 'score ' + (result.score || 0).toFixed(2));
    header.appendChild(numBadge);
    header.appendChild(srcBadge);
    header.appendChild(scoreEl);
    card.appendChild(header);

    // Title
    card.appendChild(el('div', 'source-title', chunk.title));

    // Section
    if (chunk.section) {
      card.appendChild(el('div', 'source-section', chunk.section));
    }

    // URL link (validated)
    if (url) {
      const link = document.createElement('a');
      link.className = 'source-url';
      link.href = url;
      link.rel  = 'noopener noreferrer';
      link.target = '_blank';
      link.setAttribute('aria-label', 'Open source: ' + chunk.title);
      const display = url.length > 72 ? url.slice(0, 69) + '…' : url;
      link.textContent = display;
      card.appendChild(link);
    } else {
      card.appendChild(el('span', 'source-section', 'No URL available'));
    }

    // Excerpt toggle
    if (chunk.text) {
      const excerptId = 'excerpt-' + num;
      const exToggle = el('button', 'excerpt-toggle', 'Show excerpt');
      exToggle.setAttribute('type', 'button');
      exToggle.setAttribute('aria-expanded', 'false');
      exToggle.setAttribute('aria-controls', excerptId);

      const excerpt = el('p', 'source-excerpt');
      excerpt.id = excerptId;
      excerpt.hidden = true;
      const text = chunk.text.length > 400 ? chunk.text.slice(0, 397) + '…' : chunk.text;
      excerpt.textContent = text;

      exToggle.addEventListener('click', () => {
        const open = !excerpt.hidden;
        excerpt.hidden = open;
        exToggle.textContent = open ? 'Show excerpt' : 'Hide excerpt';
        exToggle.setAttribute('aria-expanded', String(!open));
      });

      card.appendChild(exToggle);
      card.appendChild(excerpt);
    }

    list.appendChild(card);
  });

  section.appendChild(toggleBtn);
  section.appendChild(list);
  return section;
}

// ---------------------------------------------------------------------------
// Feedback
// ---------------------------------------------------------------------------
function renderFeedback(resp) {
  const section = el('div', 'feedback-section');

  const label = el('span', 'feedback-label', 'Was this helpful?');
  const btns  = el('div', 'feedback-btns');
  const upBtn   = el('button', 'thumb-btn', '👍');
  const downBtn = el('button', 'thumb-btn', '👎');
  upBtn.setAttribute('type', 'button');
  downBtn.setAttribute('type', 'button');
  upBtn.setAttribute('aria-label', 'Thumbs up – helpful');
  downBtn.setAttribute('aria-label', 'Thumbs down – not helpful');
  btns.appendChild(upBtn);
  btns.appendChild(downBtn);

  const commentArea = el('div', 'comment-area');
  commentArea.hidden = true;
  const commentInput = el('input', 'comment-input');
  commentInput.type        = 'text';
  commentInput.placeholder = 'Optional comment (what went wrong?)';
  commentInput.setAttribute('maxlength', '500');
  commentInput.setAttribute('aria-label', 'Feedback comment');
  const submitBtn = el('button', 'submit-feedback-btn', 'Send');
  submitBtn.setAttribute('type', 'button');
  commentArea.appendChild(commentInput);
  commentArea.appendChild(submitBtn);

  const doneLine = el('div', 'feedback-done', '✓ Thanks for your feedback!');
  doneLine.hidden = true;

  async function sendFeedback(rating, comment) {
    try {
      await fetch('/api/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: STATE.question,
          answer:   resp.answer,
          rating,
          comment:  comment || '',
        }),
      });
    } catch (e) { console.warn('Feedback error:', e); }

    btns.hidden        = true;
    commentArea.hidden = true;
    doneLine.hidden    = false;
    label.hidden       = true;
    toast('Feedback sent. Thank you!');
  }

  upBtn.addEventListener('click', () => {
    upBtn.classList.add('active');
    sendFeedback('up', '');
  });

  downBtn.addEventListener('click', () => {
    downBtn.classList.add('active');
    commentArea.hidden = false;
    commentInput.focus();
  });

  submitBtn.addEventListener('click', () => {
    sendFeedback('down', commentInput.value.trim());
  });

  section.appendChild(label);
  section.appendChild(btns);
  section.appendChild(commentArea);
  section.appendChild(doneLine);
  return section;
}

// ---------------------------------------------------------------------------
// Submit
// ---------------------------------------------------------------------------
async function submitQuestion() {
  const qi = document.getElementById('question-input');
  if (!qi) return;

  const question = qi.value.trim();
  if (!question) {
    qi.focus();
    return;
  }

  STATE.question = question;

  const askBtn = document.getElementById('ask-btn');
  if (askBtn) askBtn.disabled = true;

  showSkeleton();

  const filters = readFilters();
  const body = { question };
  if (filters) body.filters = filters;

  try {
    const r = await fetch('/api/ask', {
      method:  'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Session-Id': STATE.sessionId,
      },
      body: JSON.stringify(body),
    });

    if (!r.ok) {
      let detail = '';
      try { detail = (await r.json()).detail || ''; } catch {}
      showError(r.status, detail);
    } else {
      const data = await r.json();
      showAnswer(data);
    }
  } catch (e) {
    showError(0, 'Network error: ' + e.message);
  } finally {
    if (askBtn) askBtn.disabled = false;
  }
}

// ---------------------------------------------------------------------------
// Character counter + auto-grow textarea
// ---------------------------------------------------------------------------
function initTextarea() {
  const qi = document.getElementById('question-input');
  const cc = document.getElementById('char-count');
  if (!qi) return;

  qi.addEventListener('input', () => {
    const len = qi.value.length;
    const max = STATE.maxLen;
    if (cc) {
      cc.textContent = len + ' / ' + max;
      cc.classList.toggle('near-limit', len > max * 0.85);
      cc.classList.toggle('at-limit',   len >= max);
    }
    // Auto-grow
    qi.style.height = 'auto';
    qi.style.height = Math.min(qi.scrollHeight, 320) + 'px';
  });

  qi.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submitQuestion();
    }
  });
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
  loadConfig();
  initTextarea();

  document.getElementById('ask-btn')?.addEventListener('click', submitQuestion);

  // Re-render active filter tags when filters change
  document.querySelectorAll('input[name="source"]').forEach(cb => {
    cb.addEventListener('change', renderActiveTags);
  });
  document.getElementById('year-from')?.addEventListener('change', renderActiveTags);
  document.getElementById('year-to')?.addEventListener('change',   renderActiveTags);
});

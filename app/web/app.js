/* CyberLibrarian – redesigned UI, vanilla JS, zero external dependencies.
 *
 * Security contract:
 *  - ALL user-supplied or API-supplied text is set via textContent only.
 *  - URLs from the API are validated with safeUrl() before use.
 *  - NO innerHTML / outerHTML / insertAdjacentHTML / document.write / eval
 *    with dynamic data anywhere in this file.
 *  - DOM is built entirely via createElement / createElementNS.
 */

'use strict';

// ---------------------------------------------------------------------------
// Application state
// ---------------------------------------------------------------------------
const App = {
  config: null,
  messages: [],       // array of message objects
  history: [],        // [{id, question, timestamp}]
  sessionId: '',
  filters: { sources: [], yearMin: null, yearMax: null },
  sourcesData: null,  // cached from /api/sources
  currentPage: 'chat',
  showingSources: null,  // which message's sources are in the right panel
};

const EXAMPLE_QUESTIONS = [
  "What is authentication according to the OWASP Authentication Cheat Sheet?",
  "What does MITRE ATT&CK technique T1486 describe?",
  "What are the four primary defenses against SQL injection?",
  "How should passwords be hashed and stored securely?",
];

// ---------------------------------------------------------------------------
// Section: Utilities
// ---------------------------------------------------------------------------

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls)              e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

function safeUrl(url) {
  if (!url) return null;
  try {
    const u = new URL(url);
    return (u.protocol === 'http:' || u.protocol === 'https:') ? url : null;
  } catch { return null; }
}

function fmtTime(date) {
  const d = date instanceof Date ? date : new Date(date);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function getOrCreateSessionId() {
  try {
    let id = localStorage.getItem('cl_session_id');
    if (!id) {
      id = (crypto.randomUUID ? crypto.randomUUID().replace(/-/g, '') : _randomHex(32));
      localStorage.setItem('cl_session_id', id);
    }
    return id;
  } catch { return _randomHex(32); }
}

function _randomHex(n) {
  const arr = new Uint8Array(n / 2);
  crypto.getRandomValues(arr);
  return Array.from(arr, b => b.toString(16).padStart(2, '0')).join('');
}

function relativeScore(score, topScore) {
  if (!topScore || topScore <= 0) return 0;
  return Math.round((score / topScore) * 100);
}

function scoreColor(pct) {
  if (pct >= 90) return 'high';
  if (pct >= 70) return 'mid';
  return 'low';
}

function shortTag(chunk) {
  // For MITRE: extract T\d{4}(.nnn)? from chunk_id
  if (chunk.source === 'mitre') {
    const m = (chunk.chunk_id || '').match(/T\d{4}(?:\.\d{3})?/);
    if (m) return m[0];
  }
  return (chunk.source || '').toUpperCase();
}

function toast(msg, durationMs) {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = el('div', 'toast-container');
    container.id = 'toast-container';
    document.body.appendChild(container);
  }
  const t = el('div', 'toast', msg);
  container.appendChild(t);
  const delay = durationMs || 2500;
  setTimeout(() => {
    t.classList.add('fade-out');
    t.addEventListener('animationend', () => t.remove(), { once: true });
  }, delay);
}

// ---------------------------------------------------------------------------
// Section: SVG icon factory
// ---------------------------------------------------------------------------

const SVG_PATHS = {
  'shield-check': [
    ['path', 'd', 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z'],
    ['polyline', 'points', '9 12 11 14 15 10'],
  ],
  'chat': [
    ['path', 'd', 'M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z'],
  ],
  'layers': [
    ['polygon', 'points', '12 2 2 7 12 12 22 7 12 2'],
    ['polyline', 'points', '2 17 12 22 22 17'],
    ['polyline', 'points', '2 12 12 17 22 12'],
  ],
  'clock': [
    ['circle', 'cx', '12'], ['circle', 'cy', '12'], ['circle', 'r', '10'],
    ['polyline', 'points', '12 6 12 12 16 14'],
  ],
  'gear': [
    ['circle', 'cx', '12'], ['circle', 'cy', '12'], ['circle', 'r', '3'],
    ['path', 'd', 'M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z'],
  ],
  'search': [
    ['circle', 'cx', '11'], ['circle', 'cy', '11'], ['circle', 'r', '8'],
    ['line', 'x1', '21'], ['line', 'y1', '21'], ['line', 'x2', '16.65'], ['line', 'y2', '16.65'],
  ],
  'sliders': [
    ['line', 'x1', '4'], ['line', 'y1', '6'], ['line', 'x2', '20'], ['line', 'y2', '6'],
    ['line', 'x1', '8'], ['line', 'y1', '12'], ['line', 'x2', '20'], ['line', 'y2', '12'],
    ['line', 'x1', '12'], ['line', 'y1', '18'], ['line', 'x2', '20'], ['line', 'y2', '18'],
    ['circle', 'cx', '4'], ['circle', 'cy', '6'], ['circle', 'r', '2'],
    ['circle', 'cx', '8'], ['circle', 'cy', '12'], ['circle', 'r', '2'],
    ['circle', 'cx', '12'], ['circle', 'cy', '18'], ['circle', 'r', '2'],
  ],
  'send': [
    ['line', 'x1', '12'], ['line', 'y1', '19'], ['line', 'x2', '12'], ['line', 'y2', '5'],
    ['polyline', 'points', '5 12 12 5 19 12'],
  ],
  'document': [
    ['path', 'd', 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z'],
    ['polyline', 'points', '14 2 14 8 20 8'],
  ],
  'external-link': [
    ['path', 'd', 'M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6'],
    ['polyline', 'points', '15 3 21 3 21 9'],
    ['line', 'x1', '10'], ['line', 'y1', '14'], ['line', 'x2', '21'], ['line', 'y2', '3'],
  ],
  'thumbs-up': [
    ['path', 'd', 'M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3H14z'],
    ['path', 'd', 'M7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3'],
  ],
  'thumbs-down': [
    ['path', 'd', 'M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3H10z'],
    ['path', 'd', 'M17 2h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17'],
  ],
  'copy': [
    ['rect', 'x', '9'], ['rect', 'y', '9'], ['rect', 'width', '13'], ['rect', 'height', '13'], ['rect', 'rx', '2'], ['rect', 'ry', '2'],
    ['path', 'd', 'M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1'],
  ],
  'x': [
    ['line', 'x1', '18'], ['line', 'y1', '6'], ['line', 'x2', '6'], ['line', 'y2', '18'],
    ['line', 'x1', '6'], ['line', 'y1', '6'], ['line', 'x2', '18'], ['line', 'y2', '18'],
  ],
  'chevron-down': [
    ['polyline', 'points', '6 9 12 15 18 9'],
  ],
  'chevron-right': [
    ['polyline', 'points', '9 18 15 12 9 6'],
  ],
  'moon': [
    ['path', 'd', 'M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z'],
  ],
  'sun': [
    ['circle', 'cx', '12'], ['circle', 'cy', '12'], ['circle', 'r', '5'],
    ['line', 'x1', '12'], ['line', 'y1', '1'], ['line', 'x2', '12'], ['line', 'y2', '3'],
    ['line', 'x1', '12'], ['line', 'y1', '21'], ['line', 'x2', '12'], ['line', 'y2', '23'],
    ['line', 'x1', '4.22'], ['line', 'y1', '4.22'], ['line', 'x2', '5.64'], ['line', 'y2', '5.64'],
    ['line', 'x1', '18.36'], ['line', 'y1', '18.36'], ['line', 'x2', '19.78'], ['line', 'y2', '19.78'],
    ['line', 'x1', '1'], ['line', 'y1', '12'], ['line', 'x2', '3'], ['line', 'y2', '12'],
    ['line', 'x1', '21'], ['line', 'y1', '12'], ['line', 'x2', '23'], ['line', 'y2', '12'],
    ['line', 'x1', '4.22'], ['line', 'y1', '19.78'], ['line', 'x2', '5.64'], ['line', 'y2', '18.36'],
    ['line', 'x1', '18.36'], ['line', 'y1', '5.64'], ['line', 'x2', '19.78'], ['line', 'y2', '4.22'],
  ],
};

// Special icons that use different attribute patterns
const SVG_SHAPES = {
  'search': [
    { tag: 'circle', attrs: { cx: '11', cy: '11', r: '8' } },
    { tag: 'line',   attrs: { x1: '21', y1: '21', x2: '16.65', y2: '16.65' } },
  ],
  'clock': [
    { tag: 'circle',   attrs: { cx: '12', cy: '12', r: '10' } },
    { tag: 'polyline', attrs: { points: '12 6 12 12 16 14' } },
  ],
  'copy': [
    { tag: 'rect', attrs: { x: '9', y: '9', width: '13', height: '13', rx: '2', ry: '2' } },
    { tag: 'path', attrs: { d: 'M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1' } },
  ],
};

/**
 * Creates an SVG icon element safely via createElementNS.
 * @param {string} name - icon name
 * @param {number} [size=16]
 * @returns {SVGElement}
 */
function svgIcon(name, size) {
  size = size || 16;
  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns, 'svg');
  svg.setAttribute('width', String(size));
  svg.setAttribute('height', String(size));
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('fill', 'none');
  svg.setAttribute('stroke', 'currentColor');
  svg.setAttribute('stroke-width', '2');
  svg.setAttribute('stroke-linecap', 'round');
  svg.setAttribute('stroke-linejoin', 'round');
  svg.setAttribute('aria-hidden', 'true');

  const shapes = _getIconShapes(name);
  shapes.forEach(shape => {
    const child = document.createElementNS(ns, shape.tag);
    Object.entries(shape.attrs).forEach(([k, v]) => child.setAttribute(k, v));
    svg.appendChild(child);
  });

  return svg;
}

function _getIconShapes(name) {
  // Unified shape definitions
  const defs = {
    'shield-check': [
      { tag: 'path',     attrs: { d: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z' } },
      { tag: 'polyline', attrs: { points: '9 12 11 14 15 10' } },
    ],
    'chat': [
      { tag: 'path', attrs: { d: 'M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z' } },
    ],
    'layers': [
      { tag: 'polygon', attrs: { points: '12 2 2 7 12 12 22 7 12 2' } },
      { tag: 'polyline', attrs: { points: '2 17 12 22 22 17' } },
      { tag: 'polyline', attrs: { points: '2 12 12 17 22 12' } },
    ],
    'clock': [
      { tag: 'circle',   attrs: { cx: '12', cy: '12', r: '10' } },
      { tag: 'polyline', attrs: { points: '12 6 12 12 16 14' } },
    ],
    'gear': [
      { tag: 'circle', attrs: { cx: '12', cy: '12', r: '3' } },
      { tag: 'path', attrs: { d: 'M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z' } },
    ],
    'search': [
      { tag: 'circle', attrs: { cx: '11', cy: '11', r: '8' } },
      { tag: 'line',   attrs: { x1: '21', y1: '21', x2: '16.65', y2: '16.65' } },
    ],
    'sliders': [
      { tag: 'line',   attrs: { x1: '4',  y1: '6',  x2: '20', y2: '6' } },
      { tag: 'line',   attrs: { x1: '8',  y1: '12', x2: '20', y2: '12' } },
      { tag: 'line',   attrs: { x1: '12', y1: '18', x2: '20', y2: '18' } },
      { tag: 'circle', attrs: { cx: '4',  cy: '6',  r: '2' } },
      { tag: 'circle', attrs: { cx: '8',  cy: '12', r: '2' } },
      { tag: 'circle', attrs: { cx: '12', cy: '18', r: '2' } },
    ],
    'send': [
      { tag: 'line',     attrs: { x1: '12', y1: '19', x2: '12', y2: '5' } },
      { tag: 'polyline', attrs: { points: '5 12 12 5 19 12' } },
    ],
    'document': [
      { tag: 'path',     attrs: { d: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z' } },
      { tag: 'polyline', attrs: { points: '14 2 14 8 20 8' } },
    ],
    'external-link': [
      { tag: 'path',     attrs: { d: 'M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6' } },
      { tag: 'polyline', attrs: { points: '15 3 21 3 21 9' } },
      { tag: 'line',     attrs: { x1: '10', y1: '14', x2: '21', y2: '3' } },
    ],
    'thumbs-up': [
      { tag: 'path', attrs: { d: 'M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3H14z' } },
      { tag: 'path', attrs: { d: 'M7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3' } },
    ],
    'thumbs-down': [
      { tag: 'path', attrs: { d: 'M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3H10z' } },
      { tag: 'path', attrs: { d: 'M17 2h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17' } },
    ],
    'copy': [
      { tag: 'rect', attrs: { x: '9', y: '9', width: '13', height: '13', rx: '2', ry: '2' } },
      { tag: 'path', attrs: { d: 'M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1' } },
    ],
    'x': [
      { tag: 'line', attrs: { x1: '18', y1: '6',  x2: '6',  y2: '18' } },
      { tag: 'line', attrs: { x1: '6',  y1: '6',  x2: '18', y2: '18' } },
    ],
    'chevron-down': [
      { tag: 'polyline', attrs: { points: '6 9 12 15 18 9' } },
    ],
    'chevron-right': [
      { tag: 'polyline', attrs: { points: '9 18 15 12 9 6' } },
    ],
    'moon': [
      { tag: 'path', attrs: { d: 'M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z' } },
    ],
    'sun': [
      { tag: 'circle', attrs: { cx: '12', cy: '12', r: '5' } },
      { tag: 'line',   attrs: { x1: '12', y1: '1',  x2: '12', y2: '3' } },
      { tag: 'line',   attrs: { x1: '12', y1: '21', x2: '12', y2: '23' } },
      { tag: 'line',   attrs: { x1: '4.22', y1: '4.22',   x2: '5.64',  y2: '5.64' } },
      { tag: 'line',   attrs: { x1: '18.36', y1: '18.36', x2: '19.78', y2: '19.78' } },
      { tag: 'line',   attrs: { x1: '1',  y1: '12', x2: '3',  y2: '12' } },
      { tag: 'line',   attrs: { x1: '21', y1: '12', x2: '23', y2: '12' } },
      { tag: 'line',   attrs: { x1: '4.22',  y1: '19.78', x2: '5.64',  y2: '18.36' } },
      { tag: 'line',   attrs: { x1: '18.36', y1: '5.64',  x2: '19.78', y2: '4.22' } },
    ],
    'list': [
      { tag: 'line', attrs: { x1: '8',  y1: '6',  x2: '21', y2: '6' } },
      { tag: 'line', attrs: { x1: '8',  y1: '12', x2: '21', y2: '12' } },
      { tag: 'line', attrs: { x1: '8',  y1: '18', x2: '21', y2: '18' } },
      { tag: 'line', attrs: { x1: '3',  y1: '6',  x2: '3.01', y2: '6' } },
      { tag: 'line', attrs: { x1: '3',  y1: '12', x2: '3.01', y2: '12' } },
      { tag: 'line', attrs: { x1: '3',  y1: '18', x2: '3.01', y2: '18' } },
    ],
  };
  return defs[name] || [{ tag: 'circle', attrs: { cx: '12', cy: '12', r: '10' } }];
}

// ---------------------------------------------------------------------------
// Section: Safe Markdown Renderer
// ---------------------------------------------------------------------------

/**
 * Renders markdown-lite text into a DocumentFragment.
 * NEVER uses innerHTML.
 */
function renderMarkdown(text) {
  const frag = document.createDocumentFragment();
  if (!text) return frag;

  const paragraphs = text.split(/\n\n+/);
  paragraphs.forEach(para => {
    para = para.trim();
    if (!para) return;

    const lines = para.split('\n');

    // Check for bullet list
    if (lines.every(l => l.trim().startsWith('- '))) {
      const ul = document.createElement('ul');
      lines.forEach(l => {
        const li = document.createElement('li');
        _appendInlineNodes(li, l.trim().slice(2));
        ul.appendChild(li);
      });
      frag.appendChild(ul);
      return;
    }

    // Check for ordered list
    if (lines.every(l => /^\d+\.\s/.test(l.trim()))) {
      const ol = document.createElement('ol');
      lines.forEach(l => {
        const li = document.createElement('li');
        _appendInlineNodes(li, l.trim().replace(/^\d+\.\s/, ''));
        ol.appendChild(li);
      });
      frag.appendChild(ol);
      return;
    }

    // Mixed lines – wrap each as <p>
    const p = document.createElement('p');
    _appendInlineNodes(p, para);
    frag.appendChild(p);
  });

  return frag;
}

function _appendInlineNodes(parent, text) {
  // Tokenize: **bold**, `code`, [N] citation, plain
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
      const chip = el('a', 'cite-chip');
      chip.href = '#source-card-' + n;
      chip.setAttribute('aria-label', 'Source ' + n);
      chip.textContent = '[' + n + ']';
      chip.addEventListener('click', e => {
        e.preventDefault();
        highlightSourceCard(n);
      });
      parent.appendChild(chip);
    } else if (m[4] !== undefined) {
      parent.appendChild(document.createTextNode(m[4]));
    }
  }
}

// ---------------------------------------------------------------------------
// Section: Theme
// ---------------------------------------------------------------------------

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  try { localStorage.setItem('cl_theme', theme); } catch {}
  // Update the menu toggle label
  const lbl = document.getElementById('theme-toggle-label');
  if (lbl) lbl.textContent = theme === 'dark' ? 'Light mode' : 'Dark mode';
  // Update moon/sun icon in the menu button
  const menuIcon = document.querySelector('#theme-toggle-menu .menu-icon');
  if (menuIcon) {
    while (menuIcon.firstChild) menuIcon.removeChild(menuIcon.firstChild);
    const newShapes = _getIconShapes(theme === 'dark' ? 'sun' : 'moon');
    const ns = 'http://www.w3.org/2000/svg';
    newShapes.forEach(shape => {
      const child = document.createElementNS(ns, shape.tag);
      Object.entries(shape.attrs).forEach(([k, v]) => child.setAttribute(k, v));
      menuIcon.appendChild(child);
    });
  }
}

function toggleTheme() {
  const current = document.documentElement.dataset.theme || 'dark';
  applyTheme(current === 'dark' ? 'light' : 'dark');
}

function initTheme() {
  let saved = 'dark';
  try { saved = localStorage.getItem('cl_theme') || 'dark'; } catch {}
  applyTheme(saved);
}

// ---------------------------------------------------------------------------
// Section: Config Load
// ---------------------------------------------------------------------------

async function loadConfig() {
  try {
    const r = await fetch('/api/config');
    if (!r.ok) return;
    App.config = await r.json();
    const cfg = App.config;

    // Max question length
    const qi = document.getElementById('question-input');
    if (qi && cfg.max_question_len) qi.maxLength = cfg.max_question_len;

    // Mock mode pill
    const pill = document.getElementById('mode-pill');
    if (pill) {
      if (cfg.mock_mode) { pill.hidden = false; }
      else               { pill.hidden = true;  }
    }

    // Test round in sidebar footer
    if (cfg.test_round) {
      const footer = document.getElementById('sidebar-footer');
      if (footer) {
        const tag = el('span', 'test-round-tag', cfg.test_round);
        footer.appendChild(tag);
      }
    }

    // Admin download links
    if (cfg.admin_mode) {
      const adminLinks = document.getElementById('admin-links');
      if (adminLinks) {
        const files = [
          { name: 'usage_log.jsonl', label: 'Download usage log' },
          { name: 'feedback.jsonl',  label: 'Download feedback' },
        ];
        files.forEach(f => {
          const a = el('a', 'menu-item admin-link', f.label);
          a.href = '/api/admin/download/' + f.name;
          a.download = f.name;
          a.setAttribute('role', 'menuitem');
          adminLinks.appendChild(a);
        });
      }
    }

    // Year-to default
    const yearTo = document.getElementById('fp-year-to');
    if (yearTo) {
      const now = new Date().getFullYear();
      yearTo.value = now;
      yearTo.max = now;
    }

    // Example questions in empty state
    renderEmptyState();

  } catch (e) {
    console.warn('Config load failed:', e);
  }
}

// ---------------------------------------------------------------------------
// Section: Navigation / Page Routing
// ---------------------------------------------------------------------------

const NAV_ITEMS = [
  { page: 'chat',     label: 'Chat',           icon: 'chat' },
  { page: 'kb',       label: 'Knowledge Base',  icon: 'layers' },
  { page: 'history',  label: 'History',         icon: 'clock' },
  { page: 'settings', label: 'Settings',        icon: 'gear' },
];

function buildSidebar() {
  const navList = document.getElementById('sidebar-nav');
  if (!navList) return;

  NAV_ITEMS.forEach(item => {
    const li = document.createElement('li');
    li.setAttribute('role', 'listitem');

    const btn = el('button', 'nav-item');
    btn.type = 'button';
    btn.dataset.page = item.page;
    btn.dataset.tooltip = item.label;
    btn.setAttribute('aria-label', item.label);

    btn.appendChild(svgIcon(item.icon, 18));

    const lbl = el('span', 'nav-label', item.label);
    btn.appendChild(lbl);

    btn.addEventListener('click', () => navigate(item.page));
    li.appendChild(btn);
    navList.appendChild(li);
  });
}

function buildBottomTabs() {
  const nav = document.getElementById('bottom-tabs');
  if (!nav) return;

  NAV_ITEMS.forEach(item => {
    const btn = el('button', 'tab-btn');
    btn.type = 'button';
    btn.dataset.page = item.page;
    btn.setAttribute('aria-label', item.label);

    btn.appendChild(svgIcon(item.icon, 20));
    btn.appendChild(el('span', null, item.label));

    btn.addEventListener('click', () => navigate(item.page));
    nav.appendChild(btn);
  });
}

function navigate(page) {
  App.currentPage = page;

  // Update sidebar active state
  document.querySelectorAll('.nav-item[data-page]').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.page === page);
  });

  // Update bottom tabs active state
  document.querySelectorAll('.tab-btn[data-page]').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.page === page);
  });

  // Show/hide right sources panel
  const sourcesPanel = document.getElementById('sources-panel');
  if (sourcesPanel) {
    sourcesPanel.style.display = page === 'chat' ? '' : 'none';
  }

  // Show/hide shell column for sources panel in CSS grid
  const shell = document.getElementById('shell');
  if (shell) {
    shell.dataset.page = page;
  }

  const center = document.getElementById('center');
  if (!center) return;

  if (page === 'chat') {
    // Show chat view, remove any other views
    _clearNonChatViews(center);
    const chatView = document.getElementById('chat-view');
    if (chatView) {
      chatView.style.display = 'flex';
    }
    return;
  }

  // Hide chat view for other pages
  const chatView = document.getElementById('chat-view');
  if (chatView) chatView.style.display = 'none';

  _clearNonChatViews(center);

  const pageEl = el('div', 'view active-view page-view');
  pageEl.id = 'page-' + page;
  center.appendChild(pageEl);

  if (page === 'kb')       renderKBPage('', pageEl);
  if (page === 'history')  renderHistoryPage(pageEl);
  if (page === 'settings') renderSettingsPage(pageEl);
}

function _clearNonChatViews(center) {
  center.querySelectorAll('.page-view').forEach(v => v.remove());
}

// ---------------------------------------------------------------------------
// Section: Chat Interface
// ---------------------------------------------------------------------------

let _typingRow = null;

function appendMessage(msg) {
  App.messages.push(msg);
  const container = document.getElementById('chat-messages');
  if (!container) return;

  // Remove empty state if present
  const empty = container.querySelector('.empty-state');
  if (empty) empty.remove();

  const row = renderMessage(msg);
  container.appendChild(row);
  row.scrollIntoView({ behavior: 'smooth', block: 'end' });

  return row;
}

function renderEmptyState() {
  const container = document.getElementById('chat-messages');
  if (!container || App.messages.length > 0) return;

  // Don't add duplicate empty state
  if (container.querySelector('.empty-state')) return;

  const state = el('div', 'empty-state');

  const iconWrap = el('div', 'empty-state-icon');
  iconWrap.appendChild(svgIcon('shield-check', 52));
  state.appendChild(iconWrap);

  state.appendChild(el('h2', null, 'Ask about OWASP, NIST and MITRE ATT&CK'));
  state.appendChild(el('p', null, 'Get AI-powered answers grounded in cybersecurity standards and threat intelligence.'));

  const chips = el('div', 'example-chips');
  const questions = (App.config && App.config.example_questions && App.config.example_questions.length)
    ? App.config.example_questions
    : EXAMPLE_QUESTIONS;

  questions.slice(0, 4).forEach(q => {
    const chip = el('button', 'example-chip');
    chip.type = 'button';
    chip.setAttribute('aria-label', 'Ask: ' + q);
    chip.textContent = q.length > 70 ? q.slice(0, 67) + '…' : q;
    chip.addEventListener('click', () => fillAndSubmit(q));
    chips.appendChild(chip);
  });

  state.appendChild(chips);
  container.appendChild(state);
}

function renderMessage(msg) {
  const row = el('div', 'msg-row ' + msg.role);
  row.id = 'msg-' + msg.id;

  // Avatar
  const avatar = el('div', 'msg-avatar ' + (msg.role === 'user' ? 'user-avatar-icon' : 'asst-avatar'));
  if (msg.role === 'user') {
    avatar.textContent = 'G';
  } else if (msg.role === 'error') {
    avatar.appendChild(svgIcon('shield-check', 18));
    avatar.classList.add('asst-avatar');
  } else {
    avatar.appendChild(svgIcon('shield-check', 18));
  }

  const contentWrap = el('div', 'msg-content-wrap');

  if (msg.role === 'user') {
    const bubble = el('div', 'bubble user');
    const bodyFrag = renderMarkdown(msg.text);
    bubble.appendChild(bodyFrag);

    const footer = el('div', 'msg-footer');
    footer.appendChild(el('span', 'msg-ts', fmtTime(msg.timestamp)));
    contentWrap.appendChild(bubble);
    contentWrap.appendChild(footer);

  } else if (msg.role === 'assistant') {
    const bubble = el('div', 'bubble assistant');

    // Answer body
    const body = el('div', 'answer-body');
    body.appendChild(renderMarkdown(msg.answer));
    bubble.appendChild(body);

    // Grounded-in chips
    if (msg.citations && msg.citations.length > 0) {
      const gi = el('div', 'grounded-in');
      gi.appendChild(el('span', 'grounded-label', 'Answer grounded in sources:'));
      msg.citations.forEach((cit, idx) => {
        const chip = el('button', 'grounded-chip');
        chip.type = 'button';
        const num = idx + 1;
        chip.textContent = '[' + num + '] ' + cit.tag;
        chip.setAttribute('aria-label', 'Go to source ' + num);
        chip.addEventListener('click', () => highlightSourceCard(num));
        gi.appendChild(chip);
      });
      bubble.appendChild(gi);
    }

    // Message footer
    const footer = el('div', 'msg-footer');
    footer.appendChild(el('span', 'msg-ts', fmtTime(msg.timestamp)));

    if (msg.latency_ms !== undefined) {
      const meta = el('span', 'msg-meta');
      meta.appendChild(el('span', 'meta-sep', '·'));
      meta.appendChild(el('span', null, msg.latency_ms + ' ms'));
      if (msg.tokens) {
        meta.appendChild(el('span', 'meta-sep', '·'));
        meta.appendChild(el('span', null, msg.tokens + ' tok'));
      }
      if (msg.cost !== undefined) {
        meta.appendChild(el('span', 'meta-sep', '·'));
        meta.appendChild(el('span', null, '$' + (msg.cost || 0).toFixed(4)));
      }
      footer.appendChild(meta);
    }

    if (msg.cache_hit) {
      footer.appendChild(el('span', 'cache-badge', 'CACHED'));
    }

    // Action buttons
    const actions = el('div', 'msg-actions');

    const upBtn = el('button', 'action-btn', '');
    upBtn.type = 'button';
    upBtn.setAttribute('aria-label', 'Helpful');
    upBtn.appendChild(svgIcon('thumbs-up', 14));
    upBtn.addEventListener('click', () => sendFeedback(msg, 'up', upBtn, downBtn));

    const downBtn = el('button', 'action-btn', '');
    downBtn.type = 'button';
    downBtn.setAttribute('aria-label', 'Not helpful');
    downBtn.appendChild(svgIcon('thumbs-down', 14));
    downBtn.addEventListener('click', () => sendFeedback(msg, 'down', upBtn, downBtn));

    const copyBtn = el('button', 'action-btn', '');
    copyBtn.type = 'button';
    copyBtn.setAttribute('aria-label', 'Copy answer');
    copyBtn.appendChild(svgIcon('copy', 14));
    copyBtn.addEventListener('click', () => {
      navigator.clipboard.writeText(msg.answer || '').then(() => {
        copyBtn.classList.add('active-copy');
        toast('Copied to clipboard');
        setTimeout(() => copyBtn.classList.remove('active-copy'), 2000);
      }).catch(() => toast('Could not copy'));
    });

    actions.appendChild(upBtn);
    actions.appendChild(downBtn);
    actions.appendChild(copyBtn);
    footer.appendChild(actions);

    contentWrap.appendChild(bubble);
    contentWrap.appendChild(footer);

    // Mobile "Sources (n)" button
    if (msg.chunks && msg.chunks.length > 0) {
      const srcBtn = el('button', 'msg-sources-btn');
      srcBtn.type = 'button';
      srcBtn.appendChild(svgIcon('document', 12));
      srcBtn.appendChild(el('span', null, 'Sources (' + msg.chunks.length + ')'));
      srcBtn.addEventListener('click', () => openSourcesDrawer(msg.chunks, msg.citations));
      contentWrap.appendChild(srcBtn);
    }

  } else if (msg.role === 'error') {
    const bubble = el('div', 'bubble error');
    bubble.setAttribute('role', 'alert');
    bubble.appendChild(el('div', 'error-title', msg.title || 'Something went wrong'));
    bubble.appendChild(el('div', 'error-hint', msg.hint || 'Please try again.'));
    if (msg.detail) {
      const d = el('div', 'error-detail');
      d.textContent = msg.detail;
      bubble.appendChild(d);
    }
    if (msg.retryQuestion) {
      const retryBtn = el('button', 'retry-btn', 'Retry');
      retryBtn.type = 'button';
      retryBtn.addEventListener('click', () => submitQuestion(msg.retryQuestion));
      bubble.appendChild(retryBtn);
    }
    const footer = el('div', 'msg-footer');
    footer.appendChild(el('span', 'msg-ts', fmtTime(msg.timestamp)));
    contentWrap.appendChild(bubble);
    contentWrap.appendChild(footer);
  }

  row.appendChild(avatar);
  row.appendChild(contentWrap);
  return row;
}

function showTyping() {
  hideTyping();
  const container = document.getElementById('chat-messages');
  if (!container) return;

  _typingRow = el('div', 'msg-row assistant');
  _typingRow.id = 'typing-indicator';

  const avatar = el('div', 'msg-avatar asst-avatar');
  avatar.appendChild(svgIcon('shield-check', 18));

  const bubble = el('div', 'typing-bubble');
  for (let i = 0; i < 3; i++) {
    bubble.appendChild(el('span', 'typing-dot'));
  }

  _typingRow.appendChild(avatar);
  _typingRow.appendChild(bubble);
  container.appendChild(_typingRow);
  _typingRow.scrollIntoView({ behavior: 'smooth', block: 'end' });
}

function hideTyping() {
  if (_typingRow) {
    _typingRow.remove();
    _typingRow = null;
  }
  const existing = document.getElementById('typing-indicator');
  if (existing) existing.remove();
}

async function submitQuestion(question) {
  const qi = document.getElementById('question-input');

  // If called from retry, question is passed directly
  if (!question) {
    if (!qi) return;
    question = qi.value.trim();
  }

  if (!question) {
    if (qi) qi.focus();
    return;
  }

  // Navigate to chat if on another page
  if (App.currentPage !== 'chat') navigate('chat');

  // Add to history
  const histEntry = { id: 'h' + Date.now(), question, timestamp: new Date() };
  App.history.push(histEntry);

  // Add user message
  const msgId = 'm' + Date.now();
  appendMessage({
    id: msgId,
    role: 'user',
    text: question,
    timestamp: new Date(),
  });

  // Clear input
  if (qi) {
    qi.value = '';
    qi.style.height = '';
    qi.dispatchEvent(new Event('input'));
  }

  // Disable send button
  const sendBtn = document.getElementById('send-btn');
  if (sendBtn) sendBtn.disabled = true;

  // Show typing + skeleton sources
  showTyping();
  renderSkeletonSources();

  // Build request body
  const body = { question };
  const activeFilters = _readActiveFilters();
  if (activeFilters) body.filters = activeFilters;

  try {
    const r = await fetch('/api/ask', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Session-Id': App.sessionId,
      },
      body: JSON.stringify(body),
    });

    hideTyping();

    if (!r.ok) {
      let detail = '';
      try { detail = (await r.json()).detail || ''; } catch {}
      _appendErrorMessage(r.status, detail, question);
      clearSourcesList();
    } else {
      const data = await r.json();
      const asstId = 'a' + Date.now();
      const asstMsg = {
        id: asstId,
        role: 'assistant',
        answer: data.answer,
        citations: _buildCitationTags(data.chunks || [], data.citations || []),
        chunks: data.chunks || [],
        rawCitations: data.citations || [],
        timestamp: new Date(),
        latency_ms: data.latency_ms,
        tokens: data.tokens,
        cost: data.cost,
        cache_hit: data.cache_hit,
      };
      appendMessage(asstMsg);
      // Update history entry with answer message ID
      histEntry.answerId = asstId;
      // Render sources in right panel
      renderSources(data.chunks || [], data.citations || [], asstId);
    }
  } catch (e) {
    hideTyping();
    _appendErrorMessage(0, e.message, question);
    clearSourcesList();
  } finally {
    if (sendBtn) {
      const qi2 = document.getElementById('question-input');
      sendBtn.disabled = !(qi2 && qi2.value.trim());
    }
  }
}

function _appendErrorMessage(status, detail, question) {
  let title = 'Something went wrong';
  let hint = 'Check that the server is running and try again.';

  if (status === 429) {
    title = 'Rate limit reached';
    hint = "You've sent too many questions this hour. Please wait and try again.";
  } else if (status === 400) {
    title = 'Invalid question';
    hint = 'Your question may be too long or empty. Please shorten it and try again.';
  } else if (status === 503) {
    title = 'Backend unavailable';
    hint = 'The retrieval backend is not responding. Is the API server running?';
  }

  appendMessage({
    id: 'e' + Date.now(),
    role: 'error',
    title,
    hint,
    detail,
    retryQuestion: question,
    timestamp: new Date(),
  });
}

function _buildCitationTags(chunks, citations) {
  // For the "grounded in" section: [{tag, chunk_id}]
  return chunks.slice(0, 5).map((result, idx) => {
    const chunk = result.chunk;
    return {
      tag: shortTag(chunk) + ': ' + (chunk.title ? chunk.title.slice(0, 28) + (chunk.title.length > 28 ? '…' : '') : 'Source ' + (idx + 1)),
      chunk_id: chunk.chunk_id,
    };
  });
}

function clearSourcesList() {
  const list = document.getElementById('sources-list');
  if (list) {
    while (list.firstChild) list.removeChild(list.firstChild);

    const empty = el('div', 'sources-empty');
    empty.appendChild(svgIcon('document', 32));
    empty.appendChild(el('p', null, 'No sources to display'));
    list.appendChild(empty);
  }
  const count = document.getElementById('sources-count');
  if (count) count.hidden = true;
}

function sendFeedback(msg, rating, upBtn, downBtn) {
  if (rating === 'up') {
    upBtn.classList.add('active-up');
    downBtn.classList.remove('active-down');
  } else {
    downBtn.classList.add('active-down');
    upBtn.classList.remove('active-up');
  }

  fetch('/api/feedback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      question: _getQuestionBeforeMessage(msg.id),
      answer: msg.answer || '',
      rating,
      comment: '',
    }),
  }).then(() => toast('Feedback sent. Thank you!')).catch(() => {});
}

function _getQuestionBeforeMessage(asstId) {
  // Find the user message immediately before this assistant message
  const idx = App.messages.findIndex(m => m.id === asstId);
  if (idx > 0 && App.messages[idx - 1].role === 'user') {
    return App.messages[idx - 1].text;
  }
  return '';
}

function fillAndSubmit(q) {
  const qi = document.getElementById('question-input');
  if (qi) {
    qi.value = q;
    qi.dispatchEvent(new Event('input'));
  }
  submitQuestion(q);
}

// ---------------------------------------------------------------------------
// Section: Sources Panel
// ---------------------------------------------------------------------------

function renderSources(chunks, citations, messageId) {
  App.showingSources = messageId;

  const list = document.getElementById('sources-list');
  if (!list) return;
  while (list.firstChild) list.removeChild(list.firstChild);

  const count = document.getElementById('sources-count');
  if (count) {
    if (chunks.length > 0) {
      count.hidden = false;
      count.textContent = String(chunks.length);
    } else {
      count.hidden = true;
    }
  }

  if (!chunks.length) {
    clearSourcesList();
    return;
  }

  // Build citation map: chunk_id → url
  const citMap = {};
  (citations || []).forEach(c => { citMap[c.chunk_id] = c.url; });

  // Top score for relative scoring
  const topScore = chunks.reduce((best, r) => Math.max(best, r.score || 0), 0);

  chunks.slice(0, 5).forEach((result, idx) => {
    const card = _buildSourceCard(result, idx + 1, citMap, topScore);
    list.appendChild(card);
  });
}

function _buildSourceCard(result, num, citMap, topScore) {
  const chunk = result.chunk;
  const url = safeUrl(citMap[chunk.chunk_id] || '');
  const pct = relativeScore(result.score || 0, topScore);
  const colorClass = scoreColor(pct);

  const card = el('div', 'source-card');
  card.id = 'source-card-' + num;

  // Header: num badge + source badge + relevance badge
  const header = el('div', 'sc-header');

  const numBadge = el('span', 'sc-num', String(num));
  header.appendChild(numBadge);

  const src = (chunk.source || '').toLowerCase();
  const srcBadge = el('span', 'source-badge badge-' + src, src.toUpperCase());
  header.appendChild(srcBadge);

  const relBadge = el('span', 'rel-badge rel-' + colorClass, pct + '%');
  relBadge.classList.add('sc-rel');
  header.appendChild(relBadge);

  card.appendChild(header);

  // Title
  card.appendChild(el('div', 'sc-title', chunk.title || 'Untitled'));

  // Snippet (first 220 chars)
  const snippetText = (chunk.text || '').slice(0, 220) + ((chunk.text || '').length > 220 ? '…' : '');
  card.appendChild(el('div', 'sc-snippet', snippetText));

  // Footer: tag + external link
  const footer = el('div', 'sc-footer');
  const tag = shortTag(chunk);
  if (tag) footer.appendChild(el('span', 'sc-tag', tag));

  if (url) {
    const link = document.createElement('a');
    link.className = 'sc-ext-link';
    link.href = url;
    link.rel = 'noopener noreferrer';
    link.target = '_blank';
    link.setAttribute('aria-label', 'Open source: ' + (chunk.title || ''));
    link.appendChild(svgIcon('external-link', 12));
    link.appendChild(el('span', null, 'Open'));
    footer.appendChild(link);
  }

  card.appendChild(footer);

  // Show more toggle
  const moreToggle = el('button', 'sc-more-toggle', 'Show more');
  moreToggle.type = 'button';

  const moreContent = el('div', 'sc-more-content');
  moreContent.hidden = true;

  // Full excerpt
  if (chunk.text) {
    const excerpt = el('p', null, chunk.text.length > 600 ? chunk.text.slice(0, 597) + '…' : chunk.text);
    moreContent.appendChild(excerpt);
  }
  // Section
  if (chunk.section) {
    moreContent.appendChild(el('p', null, 'Section: ' + chunk.section));
  }
  // Raw score
  const rawScore = el('p', 'sc-raw-score', 'Score: ' + (result.score || 0).toFixed(4));
  moreContent.appendChild(rawScore);

  moreToggle.addEventListener('click', () => {
    const open = !moreContent.hidden;
    moreContent.hidden = open;
    moreToggle.textContent = open ? 'Show more' : 'Show less';
  });

  card.appendChild(moreToggle);
  card.appendChild(moreContent);

  return card;
}

function renderSkeletonSources() {
  const list = document.getElementById('sources-list');
  if (!list) return;
  while (list.firstChild) list.removeChild(list.firstChild);

  for (let i = 0; i < 3; i++) {
    const card = el('div', 'skeleton-card');
    const head = el('div', 'skeleton-line skeleton-head');
    card.appendChild(head);
    [85, 70, 75].forEach(w => {
      const line = el('div', 'skeleton-line');
      line.style.width = w + '%';
      card.appendChild(line);
    });
    list.appendChild(card);
  }
}

function highlightSourceCard(n) {
  const card = document.getElementById('source-card-' + n);
  if (!card) return;

  // Switch to chat page / make sure panel is visible
  if (App.currentPage !== 'chat') navigate('chat');

  card.classList.add('highlighted');
  card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  setTimeout(() => card.classList.remove('highlighted'), 2000);
}

// ---------------------------------------------------------------------------
// Section: Input Bar
// ---------------------------------------------------------------------------

function initInputBar() {
  const qi = document.getElementById('question-input');
  const sendBtn = document.getElementById('send-btn');
  const counter = document.getElementById('char-counter');
  if (!qi) return;

  const maxLen = () => qi.maxLength > 0 ? qi.maxLength : 500;

  qi.addEventListener('input', () => {
    const len = qi.value.length;
    const max = maxLen();

    // Auto-grow
    qi.style.height = 'auto';
    qi.style.height = Math.min(qi.scrollHeight, 200) + 'px';

    // Character counter (show when > 400)
    if (counter) {
      if (len > 400) {
        counter.hidden = false;
        counter.textContent = len + ' / ' + max;
        counter.className = 'char-counter' + (len >= max ? ' at-limit' : len > max * 0.85 ? ' near-limit' : '');
      } else {
        counter.hidden = true;
      }
    }

    // Send button state
    if (sendBtn) sendBtn.disabled = len === 0 || len > max;
  });

  qi.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!sendBtn || !sendBtn.disabled) submitQuestion();
    }
  });

  if (sendBtn) {
    sendBtn.addEventListener('click', () => submitQuestion());
  }
}

// ---------------------------------------------------------------------------
// Section: Filter Popover
// ---------------------------------------------------------------------------

function buildFilterPopover() {
  const popover = document.getElementById('filter-popover');
  if (!popover) return;

  // Sources section
  const srcSection = el('div', 'fp-section');
  srcSection.appendChild(el('p', 'fp-label', 'Sources'));
  const checks = el('div', 'fp-checkboxes');

  ['owasp', 'nist', 'mitre', 'cisa'].forEach(src => {
    const lbl = el('label', 'fp-check-label');
    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.name = 'fp-source';
    cb.value = src;
    cb.id = 'fp-cb-' + src;
    lbl.appendChild(cb);
    lbl.appendChild(el('span', 'source-badge badge-' + src, src.toUpperCase()));
    checks.appendChild(lbl);
  });

  srcSection.appendChild(checks);
  popover.appendChild(srcSection);

  // Year section
  const yearSection = el('div', 'fp-section');
  yearSection.appendChild(el('p', 'fp-label', 'Year range'));

  const yearRow = el('div', 'fp-year-row');

  const yearFrom = document.createElement('input');
  yearFrom.type = 'number';
  yearFrom.id = 'fp-year-from';
  yearFrom.className = 'fp-year-input';
  yearFrom.min = '2010';
  yearFrom.max = '2030';
  yearFrom.value = '2015';
  yearFrom.setAttribute('aria-label', 'From year');

  const sep = el('span', 'fp-year-sep', '–');

  const yearTo = document.createElement('input');
  yearTo.type = 'number';
  yearTo.id = 'fp-year-to';
  yearTo.className = 'fp-year-input';
  yearTo.min = '2010';
  yearTo.max = '2030';
  yearTo.value = String(new Date().getFullYear());
  yearTo.setAttribute('aria-label', 'To year');

  yearRow.appendChild(yearFrom);
  yearRow.appendChild(sep);
  yearRow.appendChild(yearTo);
  yearSection.appendChild(yearRow);
  popover.appendChild(yearSection);

  // Buttons
  const actions = el('div', 'fp-actions');

  const clearBtn = el('button', 'fp-btn fp-btn-clear', 'Clear');
  clearBtn.type = 'button';
  clearBtn.addEventListener('click', () => {
    popover.querySelectorAll('input[name="fp-source"]').forEach(cb => { cb.checked = false; });
    yearFrom.value = '2015';
    yearTo.value = String(new Date().getFullYear());
    _applyFilters();
  });

  const applyBtn = el('button', 'fp-btn fp-btn-apply', 'Apply');
  applyBtn.type = 'button';
  applyBtn.addEventListener('click', () => {
    _applyFilters();
    closeFilterPopover();
  });

  actions.appendChild(clearBtn);
  actions.appendChild(applyBtn);
  popover.appendChild(actions);

  // Close on outside click
  document.addEventListener('click', e => {
    const filterBtn = document.getElementById('filter-btn');
    if (!popover.hidden && !popover.contains(e.target) && e.target !== filterBtn && !filterBtn?.contains(e.target)) {
      closeFilterPopover();
    }
  });
}

function _applyFilters() {
  const popover = document.getElementById('filter-popover');
  if (!popover) return;

  const sources = Array.from(popover.querySelectorAll('input[name="fp-source"]:checked')).map(cb => cb.value);
  const yearFrom = parseInt(document.getElementById('fp-year-from')?.value, 10);
  const yearTo   = parseInt(document.getElementById('fp-year-to')?.value, 10);
  const defaultTo = new Date().getFullYear();

  App.filters.sources = sources;
  App.filters.yearMin = (!isNaN(yearFrom) && yearFrom !== 2015) ? yearFrom : null;
  App.filters.yearMax = (!isNaN(yearTo)   && yearTo  !== defaultTo) ? yearTo : null;

  renderActiveFilterTags();
  _updateFilterBadge();
}

function _readActiveFilters() {
  const f = App.filters;
  const body = {};
  if (f.sources && f.sources.length) body.source = f.sources;
  if (f.yearMin !== null) body.year_min = f.yearMin;
  if (f.yearMax !== null) body.year_max = f.yearMax;
  return Object.keys(body).length ? body : null;
}

function renderActiveFilterTags() {
  const container = document.getElementById('active-filter-tags');
  if (!container) return;
  while (container.firstChild) container.removeChild(container.firstChild);

  const f = App.filters;
  const tags = [];

  f.sources.forEach(src => {
    tags.push({
      label: src.toUpperCase(),
      remove: () => {
        f.sources = f.sources.filter(s => s !== src);
        const cb = document.getElementById('fp-cb-' + src);
        if (cb) cb.checked = false;
        renderActiveFilterTags();
        _updateFilterBadge();
      },
    });
  });

  const defaultTo = new Date().getFullYear();
  if (f.yearMin !== null || f.yearMax !== null) {
    const from = f.yearMin || 2015;
    const to   = f.yearMax || defaultTo;
    tags.push({
      label: from + '–' + to,
      remove: () => {
        f.yearMin = null;
        f.yearMax = null;
        const yf = document.getElementById('fp-year-from');
        const yt = document.getElementById('fp-year-to');
        if (yf) yf.value = '2015';
        if (yt) yt.value = String(defaultTo);
        renderActiveFilterTags();
        _updateFilterBadge();
      },
    });
  }

  tags.forEach(({ label, remove }) => {
    const tag = el('span', 'filter-tag');
    tag.setAttribute('role', 'listitem');
    tag.appendChild(el('span', null, label));
    const rm = el('button', 'filter-tag-rm', '×');
    rm.type = 'button';
    rm.setAttribute('aria-label', 'Remove filter ' + label);
    rm.addEventListener('click', remove);
    tag.appendChild(rm);
    container.appendChild(tag);
  });
}

function _updateFilterBadge() {
  const badge = document.getElementById('filter-badge');
  const filterBtn = document.getElementById('filter-btn');
  const count = App.filters.sources.length + (App.filters.yearMin !== null || App.filters.yearMax !== null ? 1 : 0);
  if (badge) {
    badge.hidden = count === 0;
    badge.textContent = String(count);
  }
  if (filterBtn) {
    filterBtn.classList.toggle('has-filters', count > 0);
  }
}

function toggleFilterPopover() {
  const popover = document.getElementById('filter-popover');
  const filterBtn = document.getElementById('filter-btn');
  if (!popover) return;
  const willOpen = popover.hidden;
  popover.hidden = !willOpen;
  if (filterBtn) filterBtn.setAttribute('aria-expanded', String(willOpen));
}

function closeFilterPopover() {
  const popover = document.getElementById('filter-popover');
  const filterBtn = document.getElementById('filter-btn');
  if (popover) popover.hidden = true;
  if (filterBtn) filterBtn.setAttribute('aria-expanded', 'false');
}

// ---------------------------------------------------------------------------
// Section: User Menu
// ---------------------------------------------------------------------------

function buildUserMenu() {
  const btn = document.getElementById('user-menu-btn');
  const menu = document.getElementById('user-menu');
  if (!btn || !menu) return;

  btn.addEventListener('click', e => {
    e.stopPropagation();
    const open = !menu.hidden;
    menu.hidden = open;
    btn.setAttribute('aria-expanded', String(!open));
  });

  document.addEventListener('click', e => {
    if (!menu.hidden && !menu.contains(e.target) && e.target !== btn) {
      menu.hidden = true;
      btn.setAttribute('aria-expanded', 'false');
    }
  });

  const themeToggle = document.getElementById('theme-toggle-menu');
  if (themeToggle) {
    themeToggle.addEventListener('click', () => {
      toggleTheme();
      menu.hidden = true;
      btn.setAttribute('aria-expanded', 'false');
    });
  }
}

// ---------------------------------------------------------------------------
// Section: Header Search
// ---------------------------------------------------------------------------

function initHeaderSearch() {
  const input = document.getElementById('header-search');
  if (!input) return;

  input.addEventListener('keydown', e => {
    if (e.key === 'Enter') {
      const query = input.value.trim();
      if (query) {
        navigate('kb');
        // slight delay to let the page render
        setTimeout(() => {
          const kbSearch = document.getElementById('kb-search-input');
          if (kbSearch) {
            kbSearch.value = query;
            kbSearch.dispatchEvent(new Event('input'));
          }
        }, 50);
        input.value = '';
      }
    }
    if (e.key === 'Escape') {
      input.blur();
      input.value = '';
    }
  });
}

// ---------------------------------------------------------------------------
// Section: KB Page
// ---------------------------------------------------------------------------

const KB_ATTRS = {
  owasp: 'Cheat Sheet Series — CC BY-SA 4.0',
  mitre: 'ATT&CK Enterprise — Apache 2.0',
  nist:  'Special Publications — Public domain',
  cisa:  'Advisories — Public domain',
};

async function renderKBPage(searchQuery, container) {
  if (!container) return;
  while (container.firstChild) container.removeChild(container.firstChild);

  container.appendChild(el('h2', 'page-title', 'Knowledge Base'));

  // Load sources data if not cached
  if (!App.sourcesData) {
    try {
      const r = await fetch('/api/sources');
      if (r.ok) App.sourcesData = await r.json();
    } catch {}
  }

  const data = App.sourcesData || { docs: [], counts: {} };

  // Source summary cards
  const grid = el('div', 'kb-source-grid');
  ['owasp', 'nist', 'mitre', 'cisa'].forEach(src => {
    const card = el('div', 'kb-source-card');
    const nameEl = el('div', 'kb-source-name source-badge badge-' + src, src.toUpperCase());
    card.appendChild(nameEl);
    const cnt = data.counts[src] || 0;
    card.appendChild(el('div', 'kb-source-count', cnt + ' document' + (cnt !== 1 ? 's' : '')));
    card.appendChild(el('div', 'kb-source-attr', KB_ATTRS[src] || ''));
    grid.appendChild(card);
  });

  container.appendChild(grid);

  // Search input
  const searchWrap = el('div', 'kb-search-wrap');
  const searchInput = document.createElement('input');
  searchInput.type = 'search';
  searchInput.id = 'kb-search-input';
  searchInput.className = 'kb-search-input';
  searchInput.placeholder = 'Filter documents by title…';
  searchInput.autocomplete = 'off';
  searchInput.value = searchQuery || '';
  searchWrap.appendChild(searchInput);
  container.appendChild(searchWrap);

  // Document list
  const docList = el('div', 'kb-doc-list');
  container.appendChild(docList);

  function renderDocs(query) {
    while (docList.firstChild) docList.removeChild(docList.firstChild);
    const q = (query || '').toLowerCase().trim();
    const filtered = q
      ? data.docs.filter(d => (d.title || '').toLowerCase().includes(q))
      : data.docs;

    if (!filtered.length) {
      docList.appendChild(el('p', null, q ? 'No documents matching "' + q + '".' : 'No documents available.'));
      return;
    }

    filtered.slice(0, 200).forEach(doc => {
      const item = el('div', 'kb-doc-item');
      const src = (doc.source || '').toLowerCase();
      item.appendChild(el('span', 'source-badge badge-' + src, src.toUpperCase()));
      item.appendChild(el('span', 'kb-doc-title', doc.title || doc.doc_id));
      docList.appendChild(item);
    });

    if (filtered.length > 200) {
      docList.appendChild(el('p', 'text-muted', '…and ' + (filtered.length - 200) + ' more.'));
    }
  }

  searchInput.addEventListener('input', () => renderDocs(searchInput.value));
  renderDocs(searchQuery || '');
}

// ---------------------------------------------------------------------------
// Section: History Page
// ---------------------------------------------------------------------------

function renderHistoryPage(container) {
  if (!container) return;
  while (container.firstChild) container.removeChild(container.firstChild);

  container.appendChild(el('h2', 'page-title', 'Conversation History'));

  if (!App.history.length) {
    container.appendChild(el('p', null, 'No conversation history in this session.'));
    return;
  }

  const list = el('div', 'history-list');
  [...App.history].reverse().forEach(entry => {
    const item = el('div', 'history-item');
    item.setAttribute('role', 'button');
    item.setAttribute('tabindex', '0');

    const q = el('div', 'history-q', entry.question.length > 80 ? entry.question.slice(0, 77) + '…' : entry.question);
    const ts = el('div', 'history-ts', fmtTime(entry.timestamp));

    item.appendChild(q);
    item.appendChild(ts);

    item.addEventListener('click', () => {
      navigate('chat');
      setTimeout(() => {
        const msgEl = document.getElementById('msg-' + entry.id);
        if (msgEl) {
          msgEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      }, 50);
    });

    item.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        item.click();
      }
    });

    list.appendChild(item);
  });

  container.appendChild(list);
}

// ---------------------------------------------------------------------------
// Section: Settings Page
// ---------------------------------------------------------------------------

function renderSettingsPage(container) {
  if (!container) return;
  while (container.firstChild) container.removeChild(container.firstChild);

  container.appendChild(el('h2', 'page-title', 'Settings'));

  // Appearance section
  const appearSection = el('div', 'settings-section');
  appearSection.appendChild(el('p', 'settings-section-title', 'Appearance'));

  const themeRow = el('div', 'settings-row');
  themeRow.appendChild(el('span', 'settings-row-label', 'Dark mode'));

  const label = document.createElement('label');
  label.className = 'toggle-switch';
  label.setAttribute('aria-label', 'Toggle dark mode');
  const cb = document.createElement('input');
  cb.type = 'checkbox';
  cb.checked = document.documentElement.dataset.theme !== 'light';
  cb.addEventListener('change', () => {
    applyTheme(cb.checked ? 'dark' : 'light');
  });
  const track = el('span', 'toggle-track');
  label.appendChild(cb);
  label.appendChild(track);
  themeRow.appendChild(label);
  appearSection.appendChild(themeRow);
  container.appendChild(appearSection);

  // Default filters section
  const filterSection = el('div', 'settings-section');
  filterSection.appendChild(el('p', 'settings-section-title', 'Default Source Filters'));

  ['owasp', 'nist', 'mitre', 'cisa'].forEach(src => {
    const row = el('div', 'settings-row');
    row.appendChild(el('span', 'source-badge badge-' + src, src.toUpperCase()));

    const lbl = document.createElement('label');
    lbl.className = 'toggle-switch';
    const inp = document.createElement('input');
    inp.type = 'checkbox';
    inp.checked = !App.filters.sources.length || App.filters.sources.includes(src);
    inp.addEventListener('change', () => {
      const all = ['owasp', 'nist', 'mitre', 'cisa'];
      if (!inp.checked) {
        if (!App.filters.sources.includes(src)) {
          // Was "all selected", now explicitly excluding this one
          App.filters.sources = all.filter(s => s !== src);
        } else {
          App.filters.sources = App.filters.sources.filter(s => s !== src);
        }
      } else {
        if (!App.filters.sources.includes(src)) App.filters.sources.push(src);
        // If all selected, clear the array (means "no filter")
        if (App.filters.sources.length === all.length) App.filters.sources = [];
      }
      // Sync filter popover checkboxes
      const fpCb = document.getElementById('fp-cb-' + src);
      if (fpCb) fpCb.checked = inp.checked;
      renderActiveFilterTags();
      _updateFilterBadge();
    });
    const track2 = el('span', 'toggle-track');
    lbl.appendChild(inp);
    lbl.appendChild(track2);
    row.appendChild(lbl);
    filterSection.appendChild(row);
  });

  container.appendChild(filterSection);

  // Conversation section
  const convSection = el('div', 'settings-section');
  convSection.appendChild(el('p', 'settings-section-title', 'Conversation'));

  const clearRow = el('div', 'settings-row');
  clearRow.appendChild(el('span', 'settings-row-label', 'Clear conversation'));
  const clearBtn = el('button', 'clear-btn', 'Clear');
  clearBtn.type = 'button';
  clearBtn.addEventListener('click', () => {
    if (!confirm('Clear all messages? This cannot be undone.')) return;
    App.messages = [];
    App.history = [];
    App.showingSources = null;
    clearSourcesList();
    navigate('chat');
    // Re-render empty state
    setTimeout(renderEmptyState, 50);
    toast('Conversation cleared.');
  });
  clearRow.appendChild(clearBtn);
  convSection.appendChild(clearRow);
  container.appendChild(convSection);
}

// ---------------------------------------------------------------------------
// Section: Sources Drawer (mobile)
// ---------------------------------------------------------------------------

function openSourcesDrawer(chunks, citations) {
  const drawer = document.getElementById('sources-drawer');
  const backdrop = document.getElementById('drawer-backdrop');
  const drawerList = document.getElementById('drawer-sources-list');
  if (!drawer || !drawerList) return;

  // Populate drawer
  while (drawerList.firstChild) drawerList.removeChild(drawerList.firstChild);

  const citMap = {};
  (citations || []).forEach(c => { citMap[c.chunk_id] = c.url; });
  const topScore = (chunks || []).reduce((best, r) => Math.max(best, r.score || 0), 0);

  (chunks || []).slice(0, 5).forEach((result, idx) => {
    const card = _buildSourceCard(result, idx + 1, citMap, topScore);
    drawerList.appendChild(card);
  });

  drawer.hidden = false;
  if (backdrop) backdrop.hidden = false;
  document.body.style.overflow = 'hidden';
}

function closeSourcesDrawer() {
  const drawer = document.getElementById('sources-drawer');
  const backdrop = document.getElementById('drawer-backdrop');
  if (drawer) drawer.hidden = true;
  if (backdrop) backdrop.hidden = true;
  document.body.style.overflow = '';
}

// ---------------------------------------------------------------------------
// Section: Keyboard Shortcuts
// ---------------------------------------------------------------------------

function initKeyboardShortcuts() {
  document.addEventListener('keydown', e => {
    // '/' or Ctrl+K → focus header search
    if ((e.key === '/' || (e.ctrlKey && e.key === 'k')) && !_isInputFocused()) {
      e.preventDefault();
      document.getElementById('header-search')?.focus();
    }
    // Escape → close open popovers/dropdowns/drawer
    if (e.key === 'Escape') {
      closeFilterPopover();
      const menu = document.getElementById('user-menu');
      if (menu && !menu.hidden) {
        menu.hidden = true;
        document.getElementById('user-menu-btn')?.setAttribute('aria-expanded', 'false');
      }
      closeSourcesDrawer();
    }
  });
}

function _isInputFocused() {
  const tag = document.activeElement?.tagName?.toLowerCase();
  return tag === 'input' || tag === 'textarea' || document.activeElement?.isContentEditable;
}

// ---------------------------------------------------------------------------
// Section: Responsive Behavior
// ---------------------------------------------------------------------------

function initResponsive() {
  applyResponsive();
  window.addEventListener('resize', applyResponsive);
}

function applyResponsive() {
  const w = window.innerWidth;
  const sidebar = document.getElementById('sidebar');
  const bottomTabs = document.getElementById('bottom-tabs');
  const sourcesPanel = document.getElementById('sources-panel');
  const shell = document.getElementById('shell');

  if (!shell) return;

  if (w < 600) {
    // Mobile: bottom tabs, no sidebar, no right panel
    if (sidebar) sidebar.style.display = 'none';
    if (bottomTabs) bottomTabs.hidden = false;
    if (sourcesPanel && App.currentPage !== 'chat') sourcesPanel.style.display = 'none';
    else if (sourcesPanel) sourcesPanel.style.display = 'none'; // always hidden on mobile
    shell.style.gridTemplateColumns = '1fr';

  } else if (w < 900) {
    // Tablet: icon rail, sources as drawer
    if (sidebar) { sidebar.style.display = ''; sidebar.classList.add('icon-rail'); }
    if (bottomTabs) bottomTabs.hidden = true;
    if (sourcesPanel) sourcesPanel.style.display = 'none';
    shell.style.gridTemplateColumns = '60px 1fr';

  } else if (w < 1200) {
    // Wide tablet: icon rail, right panel visible
    if (sidebar) { sidebar.style.display = ''; sidebar.classList.add('icon-rail'); }
    if (bottomTabs) bottomTabs.hidden = true;
    if (sourcesPanel) sourcesPanel.style.display = App.currentPage === 'chat' ? '' : 'none';
    shell.style.gridTemplateColumns = '60px 1fr 360px';

  } else {
    // Desktop: full 3-column
    if (sidebar) { sidebar.style.display = ''; sidebar.classList.remove('icon-rail'); }
    if (bottomTabs) bottomTabs.hidden = true;
    if (sourcesPanel) sourcesPanel.style.display = App.currentPage === 'chat' ? '' : 'none';
    shell.style.gridTemplateColumns = '240px 1fr 360px';
  }
}

// ---------------------------------------------------------------------------
// Section: Filter button wire-up
// ---------------------------------------------------------------------------

function initFilterButton() {
  const filterBtn = document.getElementById('filter-btn');
  if (filterBtn) {
    filterBtn.addEventListener('click', e => {
      e.stopPropagation();
      toggleFilterPopover();
    });
  }
}

// ---------------------------------------------------------------------------
// Section: Drawer close button
// ---------------------------------------------------------------------------

function initDrawer() {
  const closeBtn = document.getElementById('drawer-close-btn');
  const backdrop = document.getElementById('drawer-backdrop');
  if (closeBtn) closeBtn.addEventListener('click', closeSourcesDrawer);
  if (backdrop) backdrop.addEventListener('click', closeSourcesDrawer);
}

// ---------------------------------------------------------------------------
// Section: Init
// ---------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', () => {
  App.sessionId = getOrCreateSessionId();

  initTheme();
  buildSidebar();
  buildBottomTabs();
  buildFilterPopover();
  buildUserMenu();
  initInputBar();
  initHeaderSearch();
  initFilterButton();
  initDrawer();
  initKeyboardShortcuts();
  initResponsive();

  loadConfig().then(() => {
    // Render empty state after config so example questions are available
    renderEmptyState();
  });

  navigate('chat');
});

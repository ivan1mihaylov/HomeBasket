/**
 * HomeBasket card for Home Assistant.
 *
 * Scan a barcode with the phone camera or an external scanner and the product
 * lands on your shopping list. Written against plain DOM APIs on purpose - it
 * uses no Home Assistant frontend internals, so it does not break when those
 * are renamed.
 *
 * https://github.com/ivan1mihaylov/HomeBasket-card
 */

const VERSION = '0.1.0';

/** Styles for the HomeBasket card. Plain CSS, no Home Assistant components. */

const STYLES = `
  :host {
    --hb-radius: 12px;
    --hb-gap: 12px;
    --hb-fg: var(--primary-text-color, #212121);
    --hb-muted: var(--secondary-text-color, #727272);
    --hb-accent: var(--primary-color, #03a9f4);
    --hb-danger: var(--error-color, #db4437);
    --hb-ok: var(--success-color, #43a047);
    --hb-line: var(--divider-color, rgba(127, 127, 127, 0.25));
    --hb-surface: var(--card-background-color, #fff);
    --hb-sunken: color-mix(in srgb, var(--hb-fg) 6%, transparent);
    display: block;
  }

  .card {
    background: var(--hb-surface);
    border-radius: var(--ha-card-border-radius, var(--hb-radius));
    box-shadow: var(--ha-card-box-shadow, 0 2px 4px rgba(0, 0, 0, 0.12));
    border: var(--ha-card-border-width, 1px) solid
      var(--ha-card-border-color, var(--hb-line));
    color: var(--hb-fg);
    overflow: hidden;
  }

  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--hb-gap);
    padding: 16px 16px 8px;
  }
  header h2 {
    margin: 0;
    font-size: 1.25rem;
    font-weight: 500;
    line-height: 1.3;
  }
  header .count {
    color: var(--hb-muted);
    font-size: 0.8125rem;
    white-space: nowrap;
  }

  .body { padding: 8px 16px 16px; }

  .scan-row {
    display: flex;
    gap: 8px;
    align-items: stretch;
  }
  .scan-row input {
    flex: 1 1 auto;
    min-width: 0;
    font: inherit;
    font-size: 1rem;
    color: var(--hb-fg);
    background: var(--hb-sunken);
    border: 1px solid var(--hb-line);
    border-radius: 8px;
    padding: 10px 12px;
  }
  .scan-row input:focus {
    outline: 2px solid var(--hb-accent);
    outline-offset: -1px;
  }

  button {
    font: inherit;
    color: inherit;
    background: none;
    border: none;
    cursor: pointer;
    border-radius: 8px;
  }
  button:disabled { opacity: 0.45; cursor: default; }

  .btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 10px 14px;
    border: 1px solid var(--hb-line);
    background: var(--hb-sunken);
    white-space: nowrap;
  }
  .btn.primary {
    background: var(--hb-accent);
    border-color: var(--hb-accent);
    color: var(--text-primary-color, #fff);
  }
  .btn.icon { padding: 10px; min-width: 44px; }
  button svg { width: 20px; height: 20px; fill: currentColor; }

  .result {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-top: 12px;
    padding: 10px 12px;
    border-radius: 8px;
    background: var(--hb-sunken);
    border-left: 4px solid var(--hb-accent);
  }
  .result.ok { border-left-color: var(--hb-ok); }
  .result.warn { border-left-color: var(--hb-danger); }
  .result img { width: 40px; height: 40px; object-fit: contain; border-radius: 4px; }
  .result .text { min-width: 0; }
  .result .name { font-weight: 500; overflow-wrap: anywhere; }
  .result .meta { font-size: 0.8125rem; color: var(--hb-muted); }

  .section-title {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    margin: 20px 0 8px;
    font-size: 0.8125rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--hb-muted);
  }

  .search {
    width: 100%;
    box-sizing: border-box;
    font: inherit;
    color: var(--hb-fg);
    background: var(--hb-sunken);
    border: 1px solid var(--hb-line);
    border-radius: 8px;
    padding: 8px 10px;
    margin-bottom: 8px;
  }

  .table-wrap { overflow-x: auto; }
  table { width: 100%; border-collapse: collapse; }
  th, td {
    text-align: start;
    padding: 8px 6px;
    border-bottom: 1px solid var(--hb-line);
    vertical-align: middle;
  }
  th {
    font-size: 0.75rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--hb-muted);
  }
  tr:last-child td { border-bottom: none; }
  td.code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.8125rem; color: var(--hb-muted); white-space: nowrap; }
  td.name { font-weight: 500; overflow-wrap: anywhere; }
  td.brand { color: var(--hb-muted); font-size: 0.8125rem; }
  td.actions { text-align: end; white-space: nowrap; }
  td.actions button { padding: 6px; }
  td.actions svg { width: 20px; height: 20px; fill: var(--hb-muted); }
  td.actions button:hover svg { fill: var(--hb-accent); }
  td.actions button.danger:hover svg { fill: var(--hb-danger); }

  .empty {
    padding: 24px 8px;
    text-align: center;
    color: var(--hb-muted);
    font-size: 0.875rem;
  }

  .pending li {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    padding: 8px 0;
    border-bottom: 1px solid var(--hb-line);
  }
  .pending ul { list-style: none; margin: 0; padding: 0; }
  .pending li:last-child { border-bottom: none; }
  .pending code { font-size: 0.875rem; overflow-wrap: anywhere; }
  .pending .row-actions { display: inline-flex; align-items: center; gap: 4px; }
  .pending button.danger { padding: 6px; }
  .pending button.danger svg { fill: var(--hb-muted); }
  .pending button.danger:hover svg { fill: var(--hb-danger); }

  /* Dialogs */
  .backdrop {
    position: fixed;
    inset: 0;
    z-index: 10;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 16px;
    background: rgba(0, 0, 0, 0.55);
  }
  .dialog {
    width: min(420px, 100%);
    max-height: min(90vh, 720px);
    display: flex;
    flex-direction: column;
    background: var(--hb-surface);
    color: var(--hb-fg);
    border-radius: var(--hb-radius);
    box-shadow: 0 12px 32px rgba(0, 0, 0, 0.35);
  }
  .dialog h3 { margin: 0; padding: 16px 16px 8px; font-size: 1.125rem; font-weight: 500; }
  .dialog .content { padding: 8px 16px 16px; overflow: auto; }
  .dialog .content label {
    display: block;
    margin-bottom: 4px;
    font-size: 0.8125rem;
    color: var(--hb-muted);
  }
  .dialog .content input {
    width: 100%;
    box-sizing: border-box;
    font: inherit;
    font-size: 1rem;
    color: var(--hb-fg);
    background: var(--hb-sunken);
    border: 1px solid var(--hb-line);
    border-radius: 8px;
    padding: 10px 12px;
    margin-bottom: 12px;
  }
  .dialog .actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    padding: 8px 16px 16px;
  }
  .dialog .hint { font-size: 0.8125rem; color: var(--hb-muted); margin: 0 0 12px; }

  /* Camera */
  .camera { position: relative; background: #000; border-radius: 8px; overflow: hidden; }
  .camera video { display: block; width: 100%; max-height: 60vh; object-fit: cover; }
  .camera .reticle {
    position: absolute;
    inset: 20% 10%;
    border: 2px solid rgba(255, 255, 255, 0.85);
    border-radius: 8px;
    pointer-events: none;
  }

  .toast {
    position: fixed;
    left: 50%;
    bottom: 24px;
    transform: translateX(-50%);
    z-index: 20;
    max-width: min(90vw, 420px);
    padding: 12px 16px;
    border-radius: 8px;
    background: #323232;
    color: #fff;
    font-size: 0.875rem;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  }
  .toast.error { background: var(--hb-danger); }

  @media (max-width: 420px) {
    td.brand, th.brand { display: none; }
  }
`;

/* ------------------------------------------------------------------ *
 * DOM helpers, dialogs and toasts
 * ------------------------------------------------------------------ */


const ICONS = {
  plus: 'M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z',
  camera:
    'M4 4h3l2-2h6l2 2h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zm8 3a5 5 0 1 0 0 10 5 5 0 0 0 0-10zm0 2a3 3 0 1 1 0 6 3 3 0 0 1 0-6z',
  cart:
    'M11 9h2V6h3V4h-3V1h-2v3H8v2h3v3zm-4 9a2 2 0 1 0 .001 4.001A2 2 0 0 0 7 18zm10 0a2 2 0 1 0 .001 4.001A2 2 0 0 0 17 18zM7.17 14.75l.03-.12.9-1.63h7.45a2 2 0 0 0 1.75-1.03l3.58-6.49-1.74-.96-3.59 6.48H8.53L4.27 2H1v2h2l3.6 7.59-1.35 2.44A1.99 1.99 0 0 0 7 17h12v-2H7.42a.25.25 0 0 1-.25-.25z',
  pencil:
    'M20.71 7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83zM3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25z',
  trash:
    'M9 3v1H4v2h1v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V6h1V4h-5V3H9zm2 5h2v10h-2V8zm-4 0h2v10H7V8zm8 0h2v10h-2V8z',
  close: 'M19 6.41 17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z',
};

/** Build an inline SVG icon element. */
function icon(name) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('aria-hidden', 'true');
  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  path.setAttribute('d', ICONS[name] || '');
  svg.appendChild(path);
  return svg;
}

/** Create an element with attributes, classes and children in one call. */
function el(tag, options = {}, ...children) {
  const node = document.createElement(tag);
  const { class: className, text, on, ...attrs } = options;
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  for (const [key, value] of Object.entries(attrs)) {
    if (value === undefined || value === null || value === false) continue;
    node.setAttribute(key, value === true ? '' : String(value));
  }
  for (const [event, handler] of Object.entries(on || {})) {
    node.addEventListener(event, handler);
  }
  node.append(...children.filter(Boolean));
  return node;
}

/**
 * Show a modal inside the card's shadow root.
 * `build(body, close)` fills the content; `buttons` are rendered in the footer.
 */
function openDialog(root, { title, build, buttons }) {
  const backdrop = el('div', { class: 'backdrop' });
  const dialog = el('div', { class: 'dialog', role: 'dialog', 'aria-modal': 'true' });
  const content = el('div', { class: 'content' });
  const actions = el('div', { class: 'actions' });

  const close = () => {
    document.removeEventListener('keydown', onKey);
    backdrop.remove();
  };
  const onKey = (event) => {
    if (event.key === 'Escape') close();
  };

  backdrop.addEventListener('click', (event) => {
    if (event.target === backdrop) close();
  });
  document.addEventListener('keydown', onKey);

  dialog.append(el('h3', { text: title }), content, actions);
  backdrop.appendChild(dialog);

  const cleanup = build(content, close) || (() => {});
  for (const { label, primary, onClick } of buttons) {
    actions.appendChild(
      el('button', {
        class: primary ? 'btn primary' : 'btn',
        text: label,
        on: { click: () => onClick(close) },
      }),
    );
  }

  root.appendChild(backdrop);
  content.querySelector('input')?.focus();

  return () => {
    cleanup();
    close();
  };
}

/** Ask for a single line of text. Resolves to the trimmed value, or null. */
function promptDialog(root, { title, label, value = '', hint, confirmLabel }) {
  return new Promise((resolve) => {
    let input;
    let settled = false;
    const finish = (result, close) => {
      if (settled) return;
      settled = true;
      resolve(result);
      close();
    };

    openDialog(root, {
      title,
      build: (content, close) => {
        if (hint) content.appendChild(el('p', { class: 'hint', text: hint }));
        content.appendChild(el('label', { text: label, for: 'hb-prompt' }));
        input = el('input', { id: 'hb-prompt', type: 'text', value });
        input.addEventListener('keydown', (event) => {
          if (event.key === 'Enter') finish(input.value.trim() || null, close);
        });
        content.appendChild(input);
      },
      buttons: [
        { label: 'Cancel', onClick: (close) => finish(null, close) },
        {
          label: confirmLabel || 'Save',
          primary: true,
          onClick: (close) => finish(input.value.trim() || null, close),
        },
      ],
    });
  });
}

/** Ask a yes/no question. Resolves to true when confirmed. */
function confirmDialog(root, { title, message, confirmLabel }) {
  return new Promise((resolve) => {
    let settled = false;
    const finish = (result, close) => {
      if (settled) return;
      settled = true;
      resolve(result);
      close();
    };

    openDialog(root, {
      title,
      build: (content) => {
        content.appendChild(el('p', { class: 'hint', text: message }));
      },
      buttons: [
        { label: 'Cancel', onClick: (close) => finish(false, close) },
        {
          label: confirmLabel || 'Delete',
          primary: true,
          onClick: (close) => finish(true, close),
        },
      ],
    });
  });
}

/** Show a short message at the bottom of the screen. */
function toast(root, message, isError = false) {
  root.querySelector('.toast')?.remove();
  const node = el('div', { class: isError ? 'toast error' : 'toast', text: message });
  root.appendChild(node);
  setTimeout(() => node.remove(), isError ? 5000 : 3000);
}

/* ------------------------------------------------------------------ *
 * Camera scanning
 *
 * Uses the browser's native BarcodeDetector when available (Chrome, Edge and
 * the Android Home Assistant Companion app). Browsers without it - Safari and
 * therefore iOS - can fall back to a ZXing build, but only when the card is
 * configured with an explicit `zxing_url`, so nothing is pulled from a third
 * party behind your back.
 * ------------------------------------------------------------------ */

const FORMATS = [
  'ean_13',
  'ean_8',
  'upc_a',
  'upc_e',
  'code_128',
  'code_39',
  'itf',
  'qr_code',
];

/** Report why scanning is unavailable, or null when it should work. */
function scannerUnavailableReason(config = {}) {
  if (!window.isSecureContext) {
    return 'The camera needs a secure connection. Open Home Assistant over HTTPS.';
  }
  if (!navigator.mediaDevices?.getUserMedia) {
    return 'This browser does not give web pages access to the camera.';
  }
  if (!('BarcodeDetector' in window) && !config.zxing_url) {
    return (
      'This browser has no built-in barcode detector. Type the code by hand, ' +
      'or set zxing_url in the card configuration.'
    );
  }
  return null;
}

async function createDetector(config) {
  if ('BarcodeDetector' in window) {
    const supported = await window.BarcodeDetector.getSupportedFormats();
    const formats = FORMATS.filter((format) => supported.includes(format));
    const detector = new window.BarcodeDetector(
      formats.length ? { formats } : undefined,
    );
    return async (video) => {
      const [first] = await detector.detect(video);
      return first?.rawValue || null;
    };
  }

  const zxing = await import(/* webpackIgnore: true */ config.zxing_url);
  const library = zxing.default || zxing;
  const reader = new library.BrowserMultiFormatReader();
  const canvas = document.createElement('canvas');
  return async (video) => {
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    if (!canvas.width || !canvas.height) return null;
    canvas.getContext('2d').drawImage(video, 0, 0);
    try {
      return reader.decodeFromCanvas(canvas)?.getText() || null;
    } catch {
      return null; // No barcode in this frame.
    }
  };
}

/**
 * Open the camera and resolve with the first code that is read.
 * Resolves with null when the user closes the dialog.
 */
function scanWithCamera(root, config = {}) {
  return new Promise((resolve) => {
    let stream = null;
    let timer = null;
    let settled = false;

    const stop = () => {
      clearInterval(timer);
      stream?.getTracks().forEach((track) => track.stop());
      stream = null;
    };
    const finish = (code, close) => {
      if (settled) return;
      settled = true;
      stop();
      resolve(code);
      close();
    };

    openDialog(root, {
      title: 'Scan a barcode',
      build: (content, close) => {
        const video = el('video', { playsinline: true, muted: true, autoplay: true });
        const status = el('p', { class: 'hint', text: 'Starting the camera…' });
        content.append(
          el('div', { class: 'camera' }, video, el('div', { class: 'reticle' })),
          status,
        );

        (async () => {
          try {
            stream = await navigator.mediaDevices.getUserMedia({
              video: { facingMode: { ideal: 'environment' } },
              audio: false,
            });
            video.srcObject = stream;
            await video.play();

            const detect = await createDetector(config);
            status.textContent = 'Point the camera at the barcode.';

            timer = setInterval(async () => {
              if (settled || video.readyState < 2) return;
              let code = null;
              try {
                code = await detect(video);
              } catch (err) {
                clearInterval(timer);
                status.textContent = `Scanning failed: ${err.message}`;
                return;
              }
              if (code) {
                navigator.vibrate?.(80);
                finish(code, close);
              }
            }, 300);
          } catch (err) {
            status.textContent =
              err.name === 'NotAllowedError'
                ? 'Camera access was denied. Allow it for Home Assistant and try again.'
                : `Could not start the camera: ${err.message}`;
          }
        })();

        return stop; // Runs when the dialog is dismissed.
      },
      buttons: [{ label: 'Close', onClick: (close) => finish(null, close) }],
    });
  });
}

/** The camera button for the scan row. */
function cameraButton(onClick) {
  return el(
    'button',
    { class: 'btn icon', title: 'Scan with the camera', 'aria-label': 'Scan with the camera', on: { click: onClick } },
    icon('camera'),
  );
}

/* ------------------------------------------------------------------ *
 * Product table
 * ------------------------------------------------------------------ */



/**
 * Render the mappings table.
 * `actions` carries the callbacks: onAddToList, onEdit, onDelete.
 */
function renderTable(mappings, filter, actions) {
  const needle = filter.trim().toLowerCase();
  const rows = mappings
    .filter(
      (item) =>
        !needle ||
        item.code.toLowerCase().includes(needle) ||
        (item.name || '').toLowerCase().includes(needle) ||
        (item.brand || '').toLowerCase().includes(needle),
    )
    .sort((a, b) => (a.name || '').localeCompare(b.name || ''));

  if (!rows.length) {
    return el('div', {
      class: 'empty',
      text: mappings.length
        ? 'No product matches this search.'
        : 'No products learned yet. Scan something to get started.',
    });
  }

  const body = el('tbody');
  for (const item of rows) {
    body.appendChild(
      el(
        'tr',
        {},
        el('td', { class: 'name', text: item.name || item.code }),
        el('td', { class: 'brand', text: item.brand || '' }),
        el('td', { class: 'code', text: item.code }),
        el(
          'td',
          { class: 'actions' },
          el(
            'button',
            {
              title: 'Add to the shopping list',
              'aria-label': `Add ${item.name} to the shopping list`,
              on: { click: () => actions.onAddToList(item) },
            },
            icon('cart'),
          ),
          el(
            'button',
            {
              title: 'Rename',
              'aria-label': `Rename ${item.name}`,
              on: { click: () => actions.onEdit(item) },
            },
            icon('pencil'),
          ),
          el(
            'button',
            {
              class: 'danger',
              title: 'Forget this product',
              'aria-label': `Forget ${item.name}`,
              on: { click: () => actions.onDelete(item) },
            },
            icon('trash'),
          ),
        ),
      ),
    );
  }

  return el(
    'div',
    { class: 'table-wrap' },
    el(
      'table',
      {},
      el(
        'thead',
        {},
        el(
          'tr',
          {},
          el('th', { text: 'Product' }),
          el('th', { class: 'brand', text: 'Brand' }),
          el('th', { text: 'Barcode' }),
          el('th', { text: '' }),
        ),
      ),
      body,
    ),
  );
}

/** Render the codes HomeBasket could not identify. */
function renderPending(pending, actions) {
  const list = el('ul');
  for (const item of pending) {
    list.appendChild(
      el(
        'li',
        {},
        el('code', { text: item.code }),
        el(
          'span',
          { class: 'row-actions' },
          el('button', {
            class: 'btn',
            text: 'Name it',
            on: { click: () => actions.onName(item) },
          }),
          el(
            'button',
            {
              class: 'danger',
              title: 'Discard this code',
              'aria-label': `Discard ${item.code}`,
              on: { click: () => actions.onDelete(item) },
            },
            icon('trash'),
          ),
        ),
      ),
    );
  }
  return el('div', { class: 'pending' }, list);
}

/* ------------------------------------------------------------------ *
 * The card
 * ------------------------------------------------------------------ */

const DEFAULT_CONFIG = {
  title: 'HomeBasket',
  add_on_scan: true,
  show_table: true,
  show_pending: true,
  zxing_url: null,
};

class HomeBasketCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._config = { ...DEFAULT_CONFIG };
    this._state = { mappings: [], pending: [], last_scan: null, todo_entity: null };
    this._filter = '';
    this._busy = false;
    this._unsubscribe = null;
    this._rendered = false;
  }

  /* ---------------- Lovelace plumbing ---------------- */

  static getConfigElement() {
    return document.createElement('homebasket-card-editor');
  }

  static getStubConfig() {
    return { type: 'custom:homebasket-card', title: 'HomeBasket' };
  }

  setConfig(config) {
    this._config = { ...DEFAULT_CONFIG, ...config };
    if (this._rendered) this._render();
  }

  getCardSize() {
    return this._config.show_table ? 8 : 3;
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) {
      this._build();
      this._connect();
    }
  }

  connectedCallback() {
    if (this._hass && !this._unsubscribe) this._connect();
  }

  disconnectedCallback() {
    this._unsubscribe?.then((off) => off());
    this._unsubscribe = null;
  }

  /* ---------------- Backend ---------------- */

  async _call(type, payload = {}) {
    return this._hass.connection.sendMessagePromise({ type, ...payload });
  }

  async _connect() {
    await this._refresh();
    this._unsubscribe = this._hass.connection.subscribeEvents(
      () => this._refresh(),
      'homebasket_updated',
    );
  }

  async _refresh() {
    try {
      this._state = await this._call('homebasket/state');
      this._error = null;
    } catch (err) {
      this._error =
        err?.message ||
        'HomeBasket is not set up. Add the integration under Settings → Devices & Services.';
    }
    this._render();
  }

  /* ---------------- Actions ---------------- */

  async _submit(rawCode) {
    const code = (rawCode || '').trim();
    if (!code || this._busy) return;

    this._busy = true;
    this._render();
    try {
      const result = await this._call('homebasket/scan', {
        code,
        add_to_list: this._config.add_on_scan,
      });
      if (result.status === 'unknown' && !result.name) {
        await this._askForName(code);
      } else if (result.already_on_list) {
        toast(this.shadowRoot, `${result.name} is already on the list`);
      } else if (result.added) {
        toast(this.shadowRoot, `${result.name} added to the list`);
      } else {
        toast(this.shadowRoot, `${result.name} recognised`);
      }
    } catch (err) {
      toast(this.shadowRoot, err.message || 'Scan failed', true);
    } finally {
      this._busy = false;
      this._input.value = '';
      await this._refresh();
    }
  }

  async _askForName(code, current = '') {
    const name = await promptDialog(this.shadowRoot, {
      title: current ? 'Rename product' : 'New product',
      hint: current ? `Barcode ${code}` : `Barcode ${code} is not known yet.`,
      label: 'Product name',
      value: current,
      confirmLabel: current ? 'Save' : 'Save and add',
    });
    if (!name) return;

    try {
      const result = await this._call('homebasket/mapping/save', {
        code,
        name,
        add_to_list: !current && this._config.add_on_scan,
      });
      if (result.already_on_list) {
        toast(this.shadowRoot, `${name} is already on the list`);
      } else if (result.added) {
        toast(this.shadowRoot, `${name} added to the list`);
      } else {
        toast(this.shadowRoot, `${name} saved`);
      }
    } catch (err) {
      toast(this.shadowRoot, err.message || 'Could not save', true);
    }
    await this._refresh();
  }

  async _addToList(item) {
    try {
      const result = await this._call('homebasket/list/add', { name: item.name });
      toast(
        this.shadowRoot,
        result.already_on_list
          ? `${item.name} is already on the list`
          : `${item.name} added to the list`,
      );
    } catch (err) {
      toast(this.shadowRoot, err.message || 'Could not add the item', true);
    }
  }

  async _delete(item) {
    const confirmed = await confirmDialog(this.shadowRoot, {
      title: 'Forget product',
      message: `HomeBasket will no longer recognise ${item.name || item.code}.`,
    });
    if (!confirmed) return;
    try {
      await this._call('homebasket/mapping/delete', { code: item.code });
    } catch (err) {
      toast(this.shadowRoot, err.message || 'Could not delete', true);
    }
    await this._refresh();
  }

  async _openCamera() {
    const reason = scannerUnavailableReason(this._config);
    if (reason) {
      toast(this.shadowRoot, reason, true);
      return;
    }
    const code = await scanWithCamera(this.shadowRoot, this._config);
    if (code) await this._submit(code);
  }

  /* ---------------- Rendering ---------------- */

  _build() {
    const style = document.createElement('style');
    style.textContent = STYLES;

    this._input = el('input', {
      type: 'text',
      inputmode: 'numeric',
      autocomplete: 'off',
      placeholder: 'Scan or type a barcode',
      'aria-label': 'Barcode',
    });
    this._input.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') this._submit(this._input.value);
    });

    this._addButton = el(
      'button',
      {
        class: 'btn primary icon',
        title: 'Add',
        'aria-label': 'Add',
        on: { click: () => this._submit(this._input.value) },
      },
      icon('plus'),
    );

    this._headerCount = el('span', { class: 'count' });
    this._title = el('h2');
    this._body = el('div', { class: 'body' });

    this._card = el(
      'div',
      { class: 'card' },
      el('header', {}, this._title, this._headerCount),
      this._body,
    );

    this.shadowRoot.append(style, this._card);
    this._rendered = true;
    this._render();
  }

  _render() {
    if (!this._rendered) return;

    this._title.textContent = this._config.title;
    this._headerCount.textContent = this._error
      ? ''
      : `${this._state.mappings.length} products`;
    this._addButton.disabled = this._busy;
    this._input.disabled = this._busy;

    this._body.replaceChildren();

    if (this._error) {
      this._body.appendChild(el('div', { class: 'empty', text: this._error }));
      return;
    }

    this._body.appendChild(
      el(
        'div',
        { class: 'scan-row' },
        this._input,
        this._addButton,
        cameraButton(() => this._openCamera()),
      ),
    );

    if (this._state.last_scan) this._body.appendChild(this._renderResult());

    if (this._config.show_pending && this._state.pending.length) {
      this._body.appendChild(
        el('div', { class: 'section-title' }, el('span', { text: 'Waiting for a name' })),
      );
      this._body.appendChild(
        renderPending(this._state.pending, {
          onName: (item) => this._askForName(item.code),
          onDelete: (item) => this._delete(item),
        }),
      );
    }

    if (this._config.show_table) {
      this._body.appendChild(
        el('div', { class: 'section-title' }, el('span', { text: 'Known products' })),
      );

      const search = el('input', {
        class: 'search',
        type: 'search',
        placeholder: 'Search products',
        'aria-label': 'Search products',
        value: this._filter,
      });
      search.addEventListener('input', () => {
        this._filter = search.value;
        this._renderTable();
      });

      this._tableHost = el('div');
      this._body.append(search, this._tableHost);
      this._renderTable();
    }
  }

  _renderTable() {
    this._tableHost?.replaceChildren(
      renderTable(this._state.mappings, this._filter, {
        onAddToList: (item) => this._addToList(item),
        onEdit: (item) => this._askForName(item.code, item.name),
        onDelete: (item) => this._delete(item),
      }),
    );
  }

  _renderResult() {
    const scan = this._state.last_scan;
    const status = scan.added ? 'ok' : scan.name ? '' : 'warn';
    const meta = scan.added
      ? 'Added to the shopping list'
      : scan.already_on_list
        ? 'Already on the shopping list'
        : scan.name
          ? `Recognised · ${scan.code}`
          : `Not recognised · ${scan.code}`;

    return el(
      'div',
      { class: `result ${status}`.trim() },
      scan.image ? el('img', { src: scan.image, alt: '', loading: 'lazy' }) : null,
      el(
        'div',
        { class: 'text' },
        el('div', { class: 'name', text: scan.name || scan.code }),
        el('div', { class: 'meta', text: meta }),
      ),
    );
  }
}

/* ------------------------------------------------------------------ *
 * Visual editor
 * ------------------------------------------------------------------ */

const EDITOR_FIELDS = [
  { key: 'title', label: 'Title', type: 'text' },
  { key: 'add_on_scan', label: 'Add scanned products to the shopping list', type: 'boolean' },
  { key: 'show_table', label: 'Show the known products table', type: 'boolean' },
  { key: 'show_pending', label: 'Show codes waiting for a name', type: 'boolean' },
  { key: 'zxing_url', label: 'ZXing URL (only for browsers without a barcode detector)', type: 'text' },
];

class HomeBasketCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._config = { ...DEFAULT_CONFIG };
  }

  setConfig(config) {
    this._config = { ...DEFAULT_CONFIG, ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
  }

  _update(key, value) {
    this._config = { ...this._config, [key]: value };
    this.dispatchEvent(
      new CustomEvent('config-changed', {
        detail: { config: this._config },
        bubbles: true,
        composed: true,
      }),
    );
  }

  _render() {
    const style = document.createElement('style');
    style.textContent = STYLES;

    const content = el('div', { class: 'body' });
    for (const field of EDITOR_FIELDS) {
      const value = this._config[field.key];
      if (field.type === 'boolean') {
        const input = el('input', { type: 'checkbox' });
        input.checked = Boolean(value);
        input.addEventListener('change', () => this._update(field.key, input.checked));
        content.appendChild(
          el('label', { class: 'hint' }, input, document.createTextNode(` ${field.label}`)),
        );
      } else {
        const input = el('input', { type: 'text', value: value ?? '' });
        input.addEventListener('change', () =>
          this._update(field.key, input.value.trim() || null),
        );
        content.append(el('label', { text: field.label }), input);
      }
    }

    this.shadowRoot.replaceChildren(style, content);
  }
}

customElements.define('homebasket-card', HomeBasketCard);
customElements.define('homebasket-card-editor', HomeBasketCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'homebasket-card',
  name: 'HomeBasket',
  preview: false,
  description: 'Scan barcodes straight onto your shopping list.',
  documentationURL: 'https://github.com/ivan1mihaylov/HomeBasket-card',
});

console.info(
  `%c HOMEBASKET-CARD %c ${VERSION} `,
  'color:#fff;background:#03a9f4;font-weight:700',
  'color:#03a9f4;background:#fff',
);

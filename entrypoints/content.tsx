import type { PickerMessage } from '../types/picker';

// Theme colors sourced from assets/tailwind.css (:root = light, .dark = dark)
const TOAST_THEMES = {
  dark: {
    info: { bg: '#1e1f23', text: '#e3e2e7', accent: '#4ade80', shadow: '0 6px 0 0 #14532d, 0 8px 20px rgba(0,0,0,0.4)' },
    warning: { bg: '#166534', text: '#86efac', accent: '#4ade80', shadow: '0 6px 0 0 #14532d, 0 8px 20px rgba(0,0,0,0.4)' },
    error: { bg: '#93000a', text: '#ffdad6', accent: '#ffb4ab', shadow: '0 6px 0 0 #700007, 0 8px 20px rgba(0,0,0,0.4)' },
    success: { bg: '#14532d', text: '#dcfce7', accent: '#4ade80', shadow: '0 6px 0 0 #14532d, 0 8px 20px rgba(0,0,0,0.4)' },
  },
  light: {
    info: { bg: '#e7eefe', text: '#151c27', accent: '#3b6934', shadow: '0 6px 0 0 #23501e, 0 8px 20px rgba(0,0,0,0.15)' },
    warning: { bg: '#b9eeab', text: '#002201', accent: '#3b6934', shadow: '0 6px 0 0 #23501e, 0 8px 20px rgba(0,0,0,0.15)' },
    error: { bg: '#ffdad6', text: '#410000', accent: '#ba1a1a', shadow: '0 6px 0 0 #93000a, 0 8px 20px rgba(0,0,0,0.15)' },
    success: { bg: '#c1e1c1', text: '#06210d', accent: '#49654c', shadow: '0 6px 0 0 #324d35, 0 8px 20px rgba(0,0,0,0.15)' },
  },
} as const;

const TOAST_ICONS: Record<string, string> = {
  info: '<path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm0 10.99h7c-.53 4.12-3.28 7.79-7 8.94V12H5V6.3l7-3.11v8.8z"/>',
  warning: '<path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/>',
  error: '<path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/>',
  success: '<path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>',
};

let toastTheme: 'dark' | 'light' = 'dark';
let toastTimer: ReturnType<typeof setTimeout> | null = null;
let currentToastEl: HTMLDivElement | null = null;

function getToastStyle(type: 'info' | 'warning' | 'error' | 'success') {
  return TOAST_THEMES[toastTheme][type];
}

function syncToastTheme() {
  try {
    // @ts-ignore
    chrome.storage.local.get('theme', (result) => {
      const stored = result.theme as string | undefined;
      if (stored === 'light' || stored === 'dark') toastTheme = stored;
    });
    // @ts-ignore
    chrome.storage.onChanged.addListener((changes) => {
      if (changes.theme) {
        const next = changes.theme.newValue as string;
        if (next === 'light' || next === 'dark') toastTheme = next;
      }
    });
  } catch { }
}

function showToast(message: string, type: 'info' | 'warning' | 'error' | 'success' = 'info', duration = 3500) {
  if (toastTimer) clearTimeout(toastTimer);
  if (currentToastEl) {
    currentToastEl.remove();
    currentToastEl = null;
  }

  const c = getToastStyle(type);

  const el = document.createElement('div');
  el.id = 'trabahero-toast';
  el.style.cssText = [
    'position:fixed',
    'top:12px',
    'left:12px',
    'transform:translateY(-20px)',
    'z-index:2147483648',
    'font-family:Inter,system-ui,sans-serif',
    'font-size:12px',
    'font-weight:500',
    'padding:8px 12px 8px 12px',
    'border-radius:10px',
    'line-height:1.3',
    'max-width:280px',
    'min-width:180px',
    'pointer-events:none',
    'display:flex',
    'align-items:center',
    'gap:8px',
    'box-shadow:' + c.shadow,
    'border:1px solid ' + c.accent + '40',
    'opacity:0',
    'transition:opacity .3s ease,transform .3s cubic-bezier(.4,0,.2,1)',
    'background:' + c.bg,
    'color:' + c.text,
  ].join(';');

  const accentBar = document.createElement('div');
  accentBar.style.cssText = [
    'position:absolute',
    'left:0',
    'top:0',
    'bottom:0',
    'width:5px',
    'border-radius:10px 0 0 10px',
    'background:' + c.accent,
  ].join(';');

  const iconSvg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  iconSvg.setAttribute('viewBox', '0 0 24 24');
  iconSvg.setAttribute('width', '16');
  iconSvg.setAttribute('height', '16');
  iconSvg.style.cssText = 'fill:' + c.accent + ';flex-shrink:0;';
  iconSvg.innerHTML = TOAST_ICONS[type] ?? '';

  const textSpan = document.createElement('span');
  textSpan.style.cssText = 'flex:1;line-height:1.45;letter-spacing:0.01em;';
  textSpan.textContent = message;

  el.appendChild(accentBar);
  el.appendChild(iconSvg);
  el.appendChild(textSpan);

  document.body.appendChild(el);
  currentToastEl = el;

  requestAnimationFrame(() => {
    el.style.opacity = '1';
    el.style.transform = 'translateY(0)';
  });

  toastTimer = setTimeout(() => {
    if (el) {
      el.style.opacity = '0';
      el.style.transform = 'translateY(-20px)';
      setTimeout(() => { el.remove(); if (currentToastEl === el) currentToastEl = null; }, 300);
    }
    toastTimer = null;
  }, duration);
}

function createOverlay(): HTMLDivElement {
  const el = document.createElement('div');
  el.style.cssText = [
    'position:fixed',
    'pointer-events:none',
    'z-index:2147483647',
    'background-color:rgba(15,82,186,0.12)',
    'outline:2px solid #0f52ba',
    'box-shadow:inset 0 0 0 1px rgba(15,82,186,0.3)',
    'border-radius:5px',
    'display:none',
    'transition:none',
  ].join(';');
  return el;
}

let active = false;
let overlay: HTMLDivElement | null = null;

function isWithinViewport(el: HTMLElement): boolean {
  const rect = el.getBoundingClientRect();
  const vh = window.innerHeight;
  const vw = window.innerWidth;
  return rect.top >= 0 && rect.left >= 0 && rect.bottom <= vh && rect.right <= vw;
}

function sendDeactivated() {
  const msg: PickerMessage = { source: 'trabahero-picker', action: 'PICKER_DEACTIVATED' };
  browser.runtime.sendMessage(msg).catch(() => { });
}

function activate() {
  if (active) return;
  active = true;

  overlay = createOverlay();
  document.body.append(overlay);
  overlay.style.display = '';
  document.body.style.cursor = 'crosshair';
  showToast('Click the job post to scan', 'info');

  const onMove = (e: MouseEvent) => {
    const target = e.target as HTMLElement | null;
    if (!target || target === document.body || target === document.documentElement || !overlay) {
      if (overlay) overlay.style.display = 'none';
      return;
    }
    const rect = target.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) {
      overlay.style.display = 'none';
      return;
    }
    overlay.style.display = '';
    overlay.style.top = rect.top + 'px';
    overlay.style.left = rect.left + 'px';
    overlay.style.width = rect.width + 'px';
    overlay.style.height = rect.height + 'px';
  };

  const onClick = (e: MouseEvent) => {
    if (!active) return;
    e.preventDefault();
    e.stopPropagation();

    const target = e.target as HTMLElement | null;
    if (!target) return;

    if (!isWithinViewport(target)) {
      showToast('This element extends beyond the visible area — make sure it is visible or try manual crop', 'error');
      return;
    }

    const rect = target.getBoundingClientRect();
    const text = (target.textContent ?? '').trim().slice(0, 120);
    const outerHTML = target.outerHTML.length > 500
      ? target.outerHTML.slice(0, 500) + '...'
      : target.outerHTML;

    const msg: PickerMessage = {
      source: 'trabahero-picker',
      action: 'ELEMENT_SELECTED',
      payload: {
        tagName: target.tagName.toLowerCase(),
        id: target.id || null,
        className: target.classList && target.classList.length > 0
          ? Array.from(target.classList).join('.')
          : null,
        text,
        outerHTML,
        bounds: { top: rect.top, left: rect.left, width: rect.width, height: rect.height },
      },
    };
    deactivate();
    browser.runtime.sendMessage(msg);
  };

  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Escape') {
      sendDeactivated();
      deactivate();
    }
  };

  document.addEventListener('mousemove', onMove, { passive: true });
  document.addEventListener('click', onClick, { capture: true });
  document.addEventListener('keydown', onKeyDown);

  (activate as unknown as Record<string, unknown>)._cleanup = () => {
    document.removeEventListener('mousemove', onMove);
    document.removeEventListener('click', onClick, { capture: true });
    document.removeEventListener('keydown', onKeyDown);
  };
}

function deactivate() {
  if (!active) return;
  active = false;
  document.body.style.cursor = '';
  overlay?.remove();
  overlay = null;
  const cleanup = (activate as unknown as Record<string, unknown>)._cleanup as (() => void) | undefined;
  cleanup?.();
  delete (activate as unknown as Record<string, unknown>)._cleanup;
}

// --- Manual crop state ---
let cropActive = false;
let cropBackdrop: HTMLDivElement | null = null;
let cropSelection: HTMLDivElement | null = null;
let cropStartX = 0;
let cropStartY = 0;

function activateManualCrop() {
  if (cropActive) return;
  cropActive = true;

  cropBackdrop = document.createElement('div');
  cropBackdrop.style.cssText = [
    'position:fixed',
    'top:0',
    'left:0',
    'width:100%',
    'height:100%',
    'z-index:2147483646',
    'cursor:crosshair',
    'background:rgba(0,0,0,0.05)',
  ].join(';');

  cropSelection = document.createElement('div');
  cropSelection.style.cssText = [
    'position:fixed',
    'border:2px dashed #0f52ba',
    'background:rgba(15,82,186,0.08)',
    'z-index:2147483647',
    'pointer-events:none',
    'display:none',
    'border-radius:4px',
  ].join(';');

  document.body.append(cropBackdrop, cropSelection);
  showToast('Drag to select the area to scan', 'info');

  const onMouseDown = (e: MouseEvent) => {
    cropStartX = e.clientX;
    cropStartY = e.clientY;
    cropSelection!.style.display = '';
    cropSelection!.style.left = cropStartX + 'px';
    cropSelection!.style.top = cropStartY + 'px';
    cropSelection!.style.width = '0px';
    cropSelection!.style.height = '0px';
  };

  const onMouseMove = (e: MouseEvent) => {
    if (!cropSelection || cropSelection.style.display === 'none') return;
    const x = Math.min(cropStartX, e.clientX);
    const y = Math.min(cropStartY, e.clientY);
    const w = Math.abs(e.clientX - cropStartX);
    const h = Math.abs(e.clientY - cropStartY);
    cropSelection.style.left = x + 'px';
    cropSelection.style.top = y + 'px';
    cropSelection.style.width = w + 'px';
    cropSelection.style.height = h + 'px';
  };

  const onMouseUp = (e: MouseEvent) => {
    if (!cropSelection || cropSelection.style.display === 'none') return;
    const x = Math.min(cropStartX, e.clientX);
    const y = Math.min(cropStartY, e.clientY);
    const w = Math.abs(e.clientX - cropStartX);
    const h = Math.abs(e.clientY - cropStartY);

    if (w < 10 && h < 10) return;

    deactivateManualCrop();

    const msg: PickerMessage = {
      source: 'trabahero-picker',
      action: 'AREA_SELECTED',
      payload: {
        tagName: 'manual-crop',
        id: null,
        className: null,
        text: '',
        outerHTML: '',
        bounds: { top: y, left: x, width: w, height: h },
      },
    };
    browser.runtime.sendMessage(msg);
  };

  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Escape') {
      sendDeactivated();
      deactivateManualCrop();
    }
  };

  cropBackdrop.addEventListener('mousedown', onMouseDown);
  document.addEventListener('mousemove', onMouseMove);
  document.addEventListener('mouseup', onMouseUp);
  document.addEventListener('keydown', onKeyDown);

  (activate as unknown as Record<string, unknown>)._cropCleanup = () => {
    cropBackdrop?.removeEventListener('mousedown', onMouseDown);
    document.removeEventListener('mousemove', onMouseMove);
    document.removeEventListener('mouseup', onMouseUp);
    document.removeEventListener('keydown', onKeyDown);
  };
}

function deactivateManualCrop() {
  if (!cropActive) return;
  cropActive = false;
  cropBackdrop?.remove();
  cropSelection?.remove();
  cropBackdrop = null;
  cropSelection = null;
  const cleanup = (activate as unknown as Record<string, unknown>)._cropCleanup as (() => void) | undefined;
  cleanup?.();
  delete (activate as unknown as Record<string, unknown>)._cropCleanup;
}

const FAB_THEMES = {
  dark: {
    bg: 'linear-gradient(180deg, #5eeb95 0%, #4ade80 45%, #166534 100%)',
    border: '1px solid #5eeb95',
    shadow: '0 6px 0 0 #14532d, 0 8px 15px rgba(0,0,0,0.3), inset 0 1px 0 0 rgba(255,255,255,0.4)',
    shadowActive: '0 2px 0 0 #14532d, inset 0 1px 0 0 rgba(255,255,255,0.4)',
    color: '#052e16',
  },
  light: {
    bg: 'linear-gradient(180deg, #6fbe6b 0%, #3b6934 45%, #1e4d1e 100%)',
    border: '1px solid #6fbe6b',
    shadow: '0 6px 0 0 #0f3d0f, 0 8px 15px rgba(0,0,0,0.25), inset 0 1px 0 0 rgba(255,255,255,0.35)',
    shadowActive: '0 2px 0 0 #0f3d0f, inset 0 1px 0 0 rgba(255,255,255,0.35)',
    color: '#ffffff',
  },
} as const;

function applyFabTheme(fab: HTMLDivElement, theme: 'dark' | 'light') {
  const t = FAB_THEMES[theme];
  fab.style.background = t.bg;
  fab.style.border = t.border;
  fab.style.boxShadow = t.shadow;
  fab.style.color = t.color;
  fab.onmousedown = () => { fab.style.transform = 'translateY(4px)'; fab.style.boxShadow = t.shadowActive; };
  fab.onmouseup = () => { fab.style.transform = ''; fab.style.boxShadow = t.shadow; };
  fab.onmouseleave = () => { fab.style.transform = ''; fab.style.boxShadow = t.shadow; };
}

let fabEnabled = true;

function removeFloatingButton() {
  const existing = document.getElementById('trabahero-fab');
  if (existing) existing.remove();
}

function injectFloatingButton() {
  if (!fabEnabled) return;
  if (document.getElementById('trabahero-fab') || window !== window.top) return;

  const fab = document.createElement('div');
  fab.id = 'trabahero-fab';
  fab.style.cssText = [
    'position:fixed',
    'bottom:24px',
    'right:24px',
    'width:52px',
    'height:52px',
    'border-radius:14px',
    'display:flex',
    'align-items:center',
    'justify-content:center',
    'cursor:pointer',
    'z-index:2147483647',
    'transition:transform 0.1s ease',
    'padding:0',
    'margin:0',
  ].join(';');

  const icon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  icon.setAttribute('viewBox', '0 0 24 24');
  icon.setAttribute('width', '26');
  icon.setAttribute('height', '26');
  icon.style.cssText = 'fill:currentColor;pointer-events:none;';

  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  path.setAttribute('d', 'M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm0 10.99h7c-.53 4.12-3.28 7.79-7 8.94V12H5V6.3l7-3.11v8.8z');
  icon.appendChild(path);
  fab.appendChild(icon);

  applyFabTheme(fab, 'dark');

  try {
    // @ts-ignore
    chrome.storage.local.get('theme', (result) => {
      const stored = result.theme as string | undefined;
      if (stored === 'light' || stored === 'dark') applyFabTheme(fab, stored);
    });
  } catch { }

  try {
    // @ts-ignore
    chrome.storage.onChanged.addListener((changes) => {
      if (changes.theme) {
        const next = changes.theme.newValue as 'dark' | 'light';
        if (next === 'dark' || next === 'light') applyFabTheme(fab, next);
      }
    });
  } catch { }

  fab.addEventListener('click', () => {
    if (active) return;
    activate();
    browser.runtime.sendMessage({ action: 'OPEN_SIDEPANEL_AND_PICK' });
  });

  document.body.appendChild(fab);
}

export default defineContentScript({
  matches: ['*://*/*'],
  main() {
    syncToastTheme();

    try {
      // @ts-ignore
      chrome.storage.local.get('fabEnabled', (result) => {
        fabEnabled = result.fabEnabled !== false;
        if (fabEnabled) {
          injectFloatingButton();
        }
      });
      // @ts-ignore
      chrome.storage.onChanged.addListener((changes) => {
        if (changes.fabEnabled) {
          fabEnabled = changes.fabEnabled.newValue !== false;
          if (fabEnabled) {
            injectFloatingButton();
          } else {
            removeFloatingButton();
          }
        }
      });
    } catch {
      injectFloatingButton();
    }

    browser.runtime.onMessage.addListener((msg: PickerMessage, _sender, sendResponse) => {
      if (msg.source !== 'trabahero-picker') return;

      switch (msg.action) {
        case 'START_ELEMENT_PICKER':
          if (cropActive) deactivateManualCrop();
          activate();
          sendResponse({ source: 'trabahero-picker', action: 'PICKER_ACTIVATED' });
          break;
        case 'STOP_ELEMENT_PICKER':
          deactivate();
          sendResponse({ source: 'trabahero-picker', action: 'PICKER_DEACTIVATED' });
          break;
        case 'START_MANUAL_CROP':
          if (active) deactivate();
          activateManualCrop();
          sendResponse({ source: 'trabahero-picker', action: 'MANUAL_CROP_ACTIVATED' });
          break;
        case 'STOP_MANUAL_CROP':
          deactivateManualCrop();
          sendResponse({ source: 'trabahero-picker', action: 'PICKER_DEACTIVATED' });
          break;
      }
    });
  },
});

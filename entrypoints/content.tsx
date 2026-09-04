import type { PickerMessage } from '../types/picker';

const TOAST_COLORS = {
  info: { bg: '#1e1f23', text: '#e3e2e7', border: '#e9c34980' },
  warning: { bg: '#93000a', text: '#ffdad6', border: '#ffb4ab80' },
  error: { bg: '#93000a', text: '#ffdad6', border: '#ffb4ab80' },
  success: { bg: '#af8d11', text: '#342800', border: '#e9c34980' },
} as const;

let toastTimer: ReturnType<typeof setTimeout> | null = null;

function showToast(message: string, type: keyof typeof TOAST_COLORS = 'info', duration = 3000) {
  if (toastTimer) clearTimeout(toastTimer);

  let el = document.getElementById('trabahero-toast');
  if (!el) {
    el = document.createElement('div');
    el.id = 'trabahero-toast';
    el.style.cssText = [
      'position:fixed',
      'top:16px',
      'left:16px',
      'z-index:2147483648',
      'font-family:Inter,sans-serif',
      'font-size:13px',
      'padding:12px 18px',
      'border-radius:12px',
      'line-height:1.4',
      'max-width:320px',
      'pointer-events:none',
      'box-shadow:0 8px 24px rgba(0,0,0,0.5)',
      'transition:opacity .25s ease,transform .25s ease',
    ].join(';');
    document.body.appendChild(el);
  }

  const c = TOAST_COLORS[type];
  el.textContent = message;
  el.style.background = c.bg;
  el.style.color = c.text;
  el.style.border = `1px solid ${c.border}`;
  el.style.opacity = '0';
  el.style.transform = 'translateX(-16px)';
  el.style.display = '';

  requestAnimationFrame(() => {
    el!.style.opacity = '1';
    el!.style.transform = 'translateX(0)';
  });

  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    if (el) {
      el.style.opacity = '0';
      el.style.transform = 'translateX(-16px)';
      setTimeout(() => { el?.remove(); el = null; }, 260);
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
  browser.runtime.sendMessage(msg).catch(() => {});
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
      showToast('This element extends beyond the visible area — make sure it is visible or try manual crop', 'warning');
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

function injectFloatingButton() {
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
  } catch {}

  try {
    // @ts-ignore
    chrome.storage.onChanged.addListener((changes) => {
      if (changes.theme) {
        const next = changes.theme.newValue as 'dark' | 'light';
        if (next === 'dark' || next === 'light') applyFabTheme(fab, next);
      }
    });
  } catch {}

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
    injectFloatingButton();

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

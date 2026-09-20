import type { BoundingBox } from '../../../types/picker';

export async function captureElementRegion(bounds: BoundingBox): Promise<string> {
  await new Promise((r) => setTimeout(r, 50));

  const [activeTab] = await browser.tabs.query({ active: true, currentWindow: true });
  const [tabZoom, dataUrl] = await Promise.all([
    browser.tabs.getZoom(activeTab.id!),
    browser.tabs.captureVisibleTab(activeTab.windowId, { format: 'png' }),
  ]);

  const img = await new Promise<HTMLImageElement>((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = reject;
    image.src = dataUrl;
  });

  const scale = tabZoom * (window.devicePixelRatio || 1);

  const canvas = document.createElement('canvas');
  canvas.width = Math.round(bounds.width * scale);
  canvas.height = Math.round(bounds.height * scale);
  const ctx = canvas.getContext('2d')!;

  ctx.drawImage(
    img,
    Math.round(bounds.left * scale), Math.round(bounds.top * scale),
    Math.round(bounds.width * scale), Math.round(bounds.height * scale),
    0, 0, canvas.width, canvas.height,
  );

  return canvas.toDataURL('image/png');
}

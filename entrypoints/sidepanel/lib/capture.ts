import type { BoundingBox } from '../../../types/picker';

export async function captureElementRegion(bounds: BoundingBox): Promise<string> {
  await new Promise((r) => setTimeout(r, 50));

  const win = await browser.windows.getCurrent();
  const dataUrl = await browser.tabs.captureVisibleTab(win.id!, { format: 'png' });

  const img = await new Promise<HTMLImageElement>((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = reject;
    image.src = dataUrl;
  });

  const canvas = document.createElement('canvas');
  canvas.width = bounds.width;
  canvas.height = bounds.height;
  const ctx = canvas.getContext('2d')!;

  ctx.drawImage(
    img,
    bounds.left, bounds.top, bounds.width, bounds.height,
    0, 0, bounds.width, bounds.height,
  );

  return canvas.toDataURL('image/png');
}

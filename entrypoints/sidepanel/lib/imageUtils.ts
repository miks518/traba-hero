/**
 * Long-edge cap for captured screenshots.
 *
 * This is a token-budget knob as much as a bandwidth one. Vision cost scales
 * with pixel area, and the configured model is a native reasoning model, so the
 * visual input is also what it deliberates over: a full 4-image scan at 1920px
 * sent ~8.3M pixels. At 1280px a single image is 44% of the pixels, and a
 * 1280px job advert is still normally readable.
 *
 * Raise this only if small print in dense postings starts scanning badly, and
 * expect reasoning cost to rise with it.
 */
const MAX_DIMENSION = 1280;
const JPEG_QUALITY = 0.8;

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = src;
  });
}

export async function compressImage(dataUrl: string): Promise<string> {
  const img = await loadImage(dataUrl);

  let { width, height } = img;
  if (width > MAX_DIMENSION || height > MAX_DIMENSION) {
    const scale = MAX_DIMENSION / Math.max(width, height);
    width = Math.round(width * scale);
    height = Math.round(height * scale);
  }

  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d')!;
  ctx.drawImage(img, 0, 0, width, height);
  return canvas.toDataURL('image/jpeg', JPEG_QUALITY);
}

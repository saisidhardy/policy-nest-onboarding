export interface PreparedImageResult {
  file: File;
  qualityWarning: string | null;
}

const QUARTER_TURN_MOD = 4;

function replaceExtensionWithJpg(filename: string): string {
  const dot = filename.lastIndexOf(".");
  const base = dot > 0 ? filename.slice(0, dot) : filename;
  return `${base}.jpg`;
}

function assessCanvasQuality(ctx: CanvasRenderingContext2D, width: number, height: number): string | null {
  try {
    const sampleW = Math.min(240, Math.max(32, width));
    const sampleH = Math.min(240, Math.max(32, height));
    const sampleCanvas = document.createElement("canvas");
    sampleCanvas.width = sampleW;
    sampleCanvas.height = sampleH;
    const sampleCtx = sampleCanvas.getContext("2d");
    if (!sampleCtx) return null;
    sampleCtx.drawImage(ctx.canvas, 0, 0, sampleW, sampleH);
    const { data } = sampleCtx.getImageData(0, 0, sampleW, sampleH);

    let lumaSum = 0;
    let diffSum = 0;
    let diffCount = 0;
    const pixels = sampleW * sampleH;

    for (let y = 0; y < sampleH; y += 1) {
      for (let x = 0; x < sampleW; x += 1) {
        const idx = (y * sampleW + x) * 4;
        const luma = 0.299 * data[idx] + 0.587 * data[idx + 1] + 0.114 * data[idx + 2];
        lumaSum += luma;
        if (x + 1 < sampleW) {
          const rIdx = idx + 4;
          const rLuma = 0.299 * data[rIdx] + 0.587 * data[rIdx + 1] + 0.114 * data[rIdx + 2];
          diffSum += Math.abs(luma - rLuma);
          diffCount += 1;
        }
      }
    }

    const meanLuma = pixels > 0 ? lumaSum / pixels : 128;
    const meanEdge = diffCount > 0 ? diffSum / diffCount : 12;

    if (meanLuma < 45) {
      return "Photo looks too dark. Move to brighter lighting for clearer text extraction.";
    }
    if (meanLuma > 242) {
      return "Strong glare or overexposure detected. Tilt slightly away from direct light.";
    }
    if (meanEdge < 4.5) {
      return "Low detail / soft focus detected. Hold steady so all text is sharp.";
    }
    return null;
  } catch {
    return null;
  }
}

async function decodeImageSource(
  file: File
): Promise<{ source: CanvasImageSource; width: number; height: number; cleanup: () => void } | null> {
  if (typeof window === "undefined" || typeof document === "undefined") return null;

  if (typeof createImageBitmap === "function") {
    try {
      const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
      return {
        source: bitmap,
        width: bitmap.width,
        height: bitmap.height,
        cleanup: () => bitmap.close?.(),
      };
    } catch {
      // Fallback to HTMLImageElement below
    }
  }

  return await new Promise((resolve) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      resolve({
        source: img,
        width: img.naturalWidth || img.width,
        height: img.naturalHeight || img.height,
        cleanup: () => URL.revokeObjectURL(url),
      });
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      resolve(null);
    };
    img.src = url;
  });
}

export async function normalizeAndOptimizeImage(
  file: File,
  options?: { maxDimension?: number; quarterTurns?: number }
): Promise<PreparedImageResult> {
  if (!file.type.startsWith("image/") || file.type === "image/svg+xml") {
    return { file, qualityWarning: null };
  }

  const maxDimension = options?.maxDimension ?? 1800;
  const turns = (((options?.quarterTurns ?? 0) % QUARTER_TURN_MOD) + QUARTER_TURN_MOD) % QUARTER_TURN_MOD;

  try {
    const decoded = await decodeImageSource(file);
    if (!decoded || decoded.width <= 0 || decoded.height <= 0) {
      return { file, qualityWarning: null };
    }

    try {
      const scale = Math.min(1, maxDimension / Math.max(decoded.width, decoded.height));
      const drawW = Math.max(1, Math.round(decoded.width * scale));
      const drawH = Math.max(1, Math.round(decoded.height * scale));
      const rotated = turns % 2 === 1;

      const canvas = document.createElement("canvas");
      canvas.width = rotated ? drawH : drawW;
      canvas.height = rotated ? drawW : drawH;
      const ctx = canvas.getContext("2d");
      if (!ctx) {
        return { file, qualityWarning: null };
      }

      ctx.fillStyle = "#ffffff";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.save();
      ctx.translate(canvas.width / 2, canvas.height / 2);
      ctx.rotate((turns * Math.PI) / 2);
      ctx.drawImage(decoded.source, -drawW / 2, -drawH / 2, drawW, drawH);
      ctx.restore();

      const qualityWarning = assessCanvasQuality(ctx, canvas.width, canvas.height);

      const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.9));
      if (!blob) {
        return { file, qualityWarning };
      }

      const outName = replaceExtensionWithJpg(file.name || "document.jpg");
      const outFile = new File([blob], outName, { type: "image/jpeg" });
      // Keep original file if zero rotation, already tiny JPEG, and re-encode inflated it
      if (turns === 0 && file.type === "image/jpeg" && scale === 1 && outFile.size > file.size * 1.15) {
        return { file, qualityWarning };
      }
      return { file: outFile, qualityWarning };
    } finally {
      decoded.cleanup();
    }
  } catch {
    return { file, qualityWarning: null };
  }
}

export async function rotateImageFile(file: File, quarterTurns: number): Promise<File> {
  const res = await normalizeAndOptimizeImage(file, { quarterTurns });
  return res.file;
}

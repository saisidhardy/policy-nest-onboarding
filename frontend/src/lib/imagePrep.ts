export interface PreparedImageResult {
  file: File;
  qualityWarning: string | null;
  sha256?: string;
  isBlurry?: boolean;
  hasGlare?: boolean;
  isDark?: boolean;
}

export async function computeFileSha256(file: File): Promise<string> {
  if (typeof window === "undefined" || !window.crypto || !window.crypto.subtle) {
    return `${file.name}_${file.size}_${file.lastModified}`;
  }
  try {
    const arrayBuffer = await file.arrayBuffer();
    const hashBuffer = await window.crypto.subtle.digest("SHA-256", arrayBuffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
  } catch {
    return `${file.name}_${file.size}_${file.lastModified}`;
  }
}

const QUARTER_TURN_MOD = 4;

function replaceExtensionWithJpg(filename: string): string {
  const dot = filename.lastIndexOf(".");
  const base = dot > 0 ? filename.slice(0, dot) : filename;
  return `${base}.jpg`;
}

interface CanvasQualityReport {
  warning: string | null;
  isBlurry: boolean;
  hasGlare: boolean;
  isDark: boolean;
  laplacianVariance: number;
  glareRatio: number;
}

function assessCanvasQuality(ctx: CanvasRenderingContext2D, width: number, height: number): CanvasQualityReport {
  if (width < 500 || height < 350) {
    return {
      warning: "Low image resolution. Hold camera closer to capture full details for OCR.",
      isBlurry: true,
      hasGlare: false,
      isDark: false,
      laplacianVariance: 0,
      glareRatio: 0,
    };
  }

  try {
    const sampleW = Math.min(240, Math.max(32, width));
    const sampleH = Math.min(240, Math.max(32, height));
    const sampleCanvas = document.createElement("canvas");
    sampleCanvas.width = sampleW;
    sampleCanvas.height = sampleH;
    const sampleCtx = sampleCanvas.getContext("2d");
    if (!sampleCtx) {
      return { warning: null, isBlurry: false, hasGlare: false, isDark: false, laplacianVariance: 100, glareRatio: 0 };
    }
    sampleCtx.drawImage(ctx.canvas, 0, 0, sampleW, sampleH);
    const { data } = sampleCtx.getImageData(0, 0, sampleW, sampleH);

    let lumaSum = 0;
    let glareCount = 0;
    const pixels = sampleW * sampleH;
    const gray = new Float32Array(pixels);

    for (let i = 0; i < pixels; i += 1) {
      const idx = i * 4;
      const r = data[idx];
      const g = data[idx + 1];
      const b = data[idx + 2];
      const luma = 0.299 * r + 0.587 * g + 0.114 * b;
      gray[i] = luma;
      lumaSum += luma;
      if (r > 248 && g > 248 && b > 248) {
        glareCount += 1;
      }
    }

    // 3x3 Laplacian operator for high-accuracy blur variance detection
    // Kernel: [[0, 1, 0], [1, -4, 1], [0, 1, 0]]
    let lapSum = 0;
    let lapSqSum = 0;
    let lapCount = 0;

    for (let y = 1; y < sampleH - 1; y += 1) {
      for (let x = 1; x < sampleW - 1; x += 1) {
        const c = gray[y * sampleW + x];
        const top = gray[(y - 1) * sampleW + x];
        const bot = gray[(y + 1) * sampleW + x];
        const left = gray[y * sampleW + (x - 1)];
        const right = gray[y * sampleW + (x + 1)];
        const lap = top + bot + left + right - 4 * c;
        lapSum += lap;
        lapSqSum += lap * lap;
        lapCount += 1;
      }
    }

    const lapMean = lapCount > 0 ? lapSum / lapCount : 0;
    const laplacianVariance = lapCount > 0 ? lapSqSum / lapCount - lapMean * lapMean : 100;
    const meanLuma = pixels > 0 ? lumaSum / pixels : 128;
    const glareRatio = pixels > 0 ? glareCount / pixels : 0;

    const hasGlare = glareRatio > 0.15;
    const isDark = meanLuma < 48;
    const isOverexposed = meanLuma > 245;
    const isBlurry = laplacianVariance < 28;

    let warning: string | null = null;
    if (hasGlare) {
      warning = "Direct flash glare detected (>15% specular highlights). Tilt away from light or turn camera flash OFF.";
    } else if (isDark) {
      warning = "Photo appears too dark. Capture in bright natural daylight so all document details are sharp.";
    } else if (isOverexposed) {
      warning = "High overexposure detected. Move document away from direct overhead light.";
    } else if (isBlurry) {
      warning = "Low detail / blurry focus detected (Laplacian variance low). Hold camera steady and ensure text is crisp.";
    }

    return { warning, isBlurry, hasGlare, isDark, laplacianVariance, glareRatio };
  } catch {
    return { warning: null, isBlurry: false, hasGlare: false, isDark: false, laplacianVariance: 100, glareRatio: 0 };
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

      const qualityReport = assessCanvasQuality(ctx, canvas.width, canvas.height);
      const qualityWarning = qualityReport.warning;

      const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.9));
      if (!blob) {
        return {
          file,
          qualityWarning,
          isBlurry: qualityReport.isBlurry,
          hasGlare: qualityReport.hasGlare,
          isDark: qualityReport.isDark,
        };
      }

      const outName = replaceExtensionWithJpg(file.name || "document.jpg");
      const outFile = new File([blob], outName, { type: "image/jpeg" });
      const sha256 = await computeFileSha256(outFile);

      return {
        file: outFile,
        qualityWarning,
        sha256,
        isBlurry: qualityReport.isBlurry,
        hasGlare: qualityReport.hasGlare,
        isDark: qualityReport.isDark,
      };
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

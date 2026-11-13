/**
 * Convert a Blob into a base64 data: URL so previews never rely on blob: URLs,
 * which strict reverse-proxy Content-Security-Policy headers may block.
 */
export function blobToDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === "string") {
        resolve(reader.result);
      } else {
        reject(new Error("Unable to convert preview binary payload."));
      }
    };
    reader.onerror = () => {
      reject(reader.error ?? new Error("Unable to read preview file."));
    };
    reader.readAsDataURL(blob);
  });
}

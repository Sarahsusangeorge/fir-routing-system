import type { ScanResult } from "../types";

export class ScanError extends Error {}

/**
 * Extracts text from a photographed or uploaded complaint document.
 *
 * OCR runs entirely in the browser with Tesseract.js, loaded on demand so it
 * never adds weight to the main bundle. The photo never leaves the device;
 * only the text the user reviews and submits is sent to the server.
 */
export async function scanDocument(file: File | Blob, onProgress?: (fraction: number) => void): Promise<ScanResult> {
  try {
    const { recognize } = await import("tesseract.js");
    const { data } = await recognize(file, "eng", {
      logger: (m) => {
        if (m.status === "recognizing text" && typeof m.progress === "number") {
          onProgress?.(m.progress);
        }
      },
    });

    const text = data.text.trim();
    if (!text) {
      throw new ScanError("No legible text was found in this document.");
    }
    return { extracted_text: text, confidence: data.confidence };
  } catch (err) {
    if (err instanceof ScanError) throw err;
    throw new ScanError("Unable to read this document. Try a clearer, well-lit photo.");
  }
}

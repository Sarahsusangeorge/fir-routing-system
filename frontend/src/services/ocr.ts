import type { ScanResult } from "../types";

export class ScanError extends Error {}

/**
 * Where the Tesseract worker, WebAssembly core and language data are served
 * from. Left to itself tesseract.js fetches all three from public CDNs at the
 * moment someone scans a document, which would mean third-party code running
 * inside a police system and a third party learning that a scan took place.
 * These paths keep every byte on this origin; scripts/vendor-ocr.mjs copies
 * the files out of node_modules at build time.
 */
export const OCR_ASSETS = {
  workerPath: `${import.meta.env.BASE_URL}tesseract/worker.min.js`,
  corePath: `${import.meta.env.BASE_URL}tesseract`,
  langPath: `${import.meta.env.BASE_URL}tesseract/lang`,
  /** The vendored data is uncompressed on arrival rather than fetched as .gz from a CDN. */
  gzip: true,
};

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
      ...OCR_ASSETS,
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

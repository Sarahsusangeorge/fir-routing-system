import type { ScanResult } from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string | undefined;

export class ScanError extends Error {}

/**
 * Extracts text from a photographed or uploaded FIR/complaint document.
 *
 * When a real backend is configured, the image is sent to `/api/scan` for
 * server-side OCR. Otherwise (demo mode) text is extracted client-side in
 * the browser via Tesseract.js — a real OCR engine, not a simulation —
 * loaded on demand so it never adds weight to the main bundle.
 */
export async function scanDocument(file: File | Blob, onProgress?: (fraction: number) => void): Promise<ScanResult> {
  if (API_BASE_URL) {
    try {
      const form = new FormData();
      form.append("image", file);
      const res = await fetch(`${API_BASE_URL}/api/scan`, { method: "POST", body: form });
      if (res.status === 404) {
        // The backend doesn't implement server-side OCR (yet, or at all) —
        // fall through to client-side OCR rather than treating this as a
        // failure. Any other non-2xx status is a real, reported failure.
      } else if (!res.ok) {
        const body = (await res.json().catch(() => null)) as { error?: string } | null;
        throw new ScanError(body?.error ?? "The document scanning service could not be reached.");
      } else {
        return (await res.json()) as ScanResult;
      }
    } catch (err) {
      if (err instanceof ScanError) throw err;
      // Network failure — fall through to client-side OCR below.
    }
  }

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

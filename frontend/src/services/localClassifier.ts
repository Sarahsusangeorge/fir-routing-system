import type { Complaint, ExplanationToken, Section } from "../types";
import { DEFAULT_CATEGORY, LEGAL_CATALOG, priorityLevelFromScore } from "./legalCatalog";

/**
 * Deterministic, rule-based stand-in for the classification service.
 * Used only when the real /api/classify endpoint is unavailable, so the
 * product remains fully demonstrable offline. Mirrors the response shape
 * of the live API exactly.
 */
export function classifyLocally(complaintText: string): Complaint {
  const text = complaintText.toLowerCase();

  const matches = LEGAL_CATALOG.map((category) => {
    const hits = category.keywords.filter((kw) => text.includes(kw.toLowerCase()));
    return { category, hits };
  }).filter((m) => m.hits.length > 0);

  matches.sort((a, b) => b.category.severity - a.category.severity);
  const top = matches.slice(0, 2);

  const sections: Section[] = top.length
    ? top.map(({ category, hits }, i) => ({
        code: category.code,
        title: category.title,
        confidence: Math.min(0.97, 0.68 + hits.length * 0.08 + (i === 0 ? 0.08 : 0)),
      }))
    : [{ code: DEFAULT_CATEGORY.code, title: DEFAULT_CATEGORY.title, confidence: 0.42 }];

  const primary = top[0]?.category ?? DEFAULT_CATEGORY;
  const avgConfidence = sections.reduce((s, sec) => s + sec.confidence, 0) / sections.length;
  const score = Math.min(10, Math.round(primary.severity * (0.55 + 0.45 * avgConfidence) * 10) / 10);

  const explanation: ExplanationToken[] = top.length
    ? top
        .flatMap(({ hits }, i) =>
          hits.map((token, j) => ({
            token,
            weight: Math.max(0.12, 0.5 - i * 0.15 - j * 0.09),
          }))
        )
        .sort((a, b) => b.weight - a.weight)
        .slice(0, 6)
    : [{ token: complaintText.trim().split(/\s+/).slice(0, 1)[0] ?? "complaint", weight: 0.2 }];

  return {
    complaint_id: 0,
    complaint_text: complaintText,
    received_at: new Date().toISOString(),
    sections,
    priority: { level: priorityLevelFromScore(score), score },
    routing: { unit: primary.unit, reason: primary.reason },
    explanation,
  };
}

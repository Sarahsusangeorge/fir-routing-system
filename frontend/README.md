# NIVARA — Complaint Intelligence & Resolution Platform

An AI-assisted complaint intelligence system: complaint narratives are classified against
relevant legal sections, assigned a rule-based priority, routed to the appropriate unit,
and explained through token-level model explainability.

NIVARA is a decision-support and triage tool. It does not determine guilt, innocence, or
final legal outcomes — a human reviewer always makes the final decision.

## Stack

React · TypeScript · Tailwind CSS v4 · Framer Motion · Lucide React · React Router

## Getting started

```bash
npm install
npm run dev
```

## Backend integration

The frontend expects two endpoints, configured via `VITE_API_BASE_URL` (see `.env.example`):

- `POST /api/classify` — `{ complaint_text }` → classification result
- `GET /api/complaints` — complaint history

When `VITE_API_BASE_URL` is unset, or the API is unreachable, the app runs in **demo mode**:
a local rule-based classifier (`src/services/localClassifier.ts`) and a seeded history of 18
anonymized sample complaints (`src/services/mockData.ts`) keep the product fully
demonstrable offline. Types for both the live and demo paths are shared (`src/types`), so
switching a real backend on requires no frontend changes.

## Project structure

```
src/
  components/   Reusable presentational components
  pages/        Analyze, History
  services/     API client, demo classifier, legal reference catalog
  types/        Shared TypeScript interfaces
  hooks/        useCountUp
```

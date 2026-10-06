# NIVARA: UX and Accessibility Report

**Target:** WCAG 2.2 Level AA for the citizen, officer and admin workflows.

**Method:**

1. **axe-core 4.10.2**, injected into the running app in Chromium (the built-in browser pane), with these rule tags: `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa`.
2. **Manual checks:** keyboard use, focus management, accessible names (DOM and accessibility tree), and live regions.
3. **A 375 px mobile viewport check:** horizontal overflow and touch targets under 24 px.
4. **Code review** of every page and component.

This is **not** a WCAG certification. Screen-reader testing with NVDA, JAWS or VoiceOver was **not** done.

## Automated results (axe-core, live app)

| Page | Before fixes | After fixes |
|---|---|---|
| Sign-in (`#/login`) | 1 serious: `color-contrast` (footer text 3.46:1 on dark) | fixed globally (footer) |
| Case detail, restricted case (`#/cases/15`) | 1 serious: same footer contrast | **0 violations** |
| Staff management (`#/staff`) | n/a (scanned after the fix) | **0 violations** |
| Case list, admin (`#/cases`) | n/a | **0 violations** |
| New complaint / analysis (`#/new`) | n/a | **0 violations** |

Automated tools catch only a minority of WCAG problems. The manual findings below matter more.

## Defects found and fixed

| # | WCAG / heuristic | Defect | Fix | Verified by |
|---|---|---|---|---|
| A1 | 1.4.3 Contrast (AA) | Footer text at `vellum/40` on onyx measured 3.46:1 | Raised to `vellum/75`–`/80` | axe re-scan: 0 |
| A2 | 4.1.3 Status Messages; trust | The analysis progress was **simulated**. It announced "Analysis complete" on a timer *before the request was sent*, then made the request, adding about 2 s. | The request now starts immediately. The animation holds on its last working stage until the server answers. Focus moves to the result. On error the message appears at once and the text is kept. | Code; `AnalyzePage.tsx` |
| A3 | 2.4.3 Focus Order, 2.1.2 | The scanner dialog had no focus trap, so Tab escaped behind the modal, and focus was not returned on close | Tab and Shift+Tab are trapped; Escape closes; focus returns to the control that opened it | Code (jsdom cannot test this, because there is no layout) |
| A4 | 4.1.2 Name, Role, Value | Explanation highlights were `role="button"` but performed no action | The role is removed. Each highlight is focusable with an accessible name: "*word*, influence weight 0.87" | `components.test.tsx` |
| A5 | 4.1.2; ARIA tabs pattern | Citizen / staff tabs had no `aria-controls`, the panel was not labelled, and the arrow keys did nothing | IDs, `aria-controls` and `aria-labelledby`; roving `tabIndex`; ← and → switch tabs | Live: focus and selection follow ArrowRight |
| A6 | 1.3.1; 3.3.2 | Field hints (for example "Indian mobile numbers only") were not linked to their inputs | `aria-describedby` on every sign-in field | Code |
| A7 | 2.4.6, 2.5.3 Label in Name | Five identical "Sign online instead" buttons on My complaints | Accessible name "Sign online instead, complaint #16". It keeps the visible label so voice control still works. | Live accessibility tree |
| A8 | 3.3.4 Error Prevention | "Deactivate" (which moves all open cases and ends sessions) took one click | Confirmation stating the consequences (number of cases moved, sessions ended) | Code |
| A9 | Plain language; trust | The staff page claimed "an officer assigned to a unit sees only that unit's complaints", which was false | The copy now describes the actual access rules | Code |
| A10 | Plain language | The routing card said "not manual judgment", but officers can override | "Suggested by a rule table… The handling officer can transfer the case, with a recorded reason." | Live UI |
| A11 | Plain language | After filing, the citizen was told only to sign at the station, though online signing exists | Both options explained, with the deadline | Live UI |
| A12 | 3.3.2 Labels | The staff sign-in field said "Official email" and was `type="email"`, but usernames also work | "Username or official email", plain text input | Live UI |
| A13 | Trust; decision support | No indication that the triage was uncertain, or which classifier was used | "Officer review needed" box (icon + heading + reasons, not colour alone); classifier badge; "Suggested priority… not a legal finding" | `components.test.tsx`; live UI |
| A14 | Error recovery | Network failures produced fabricated results (see NIV-02) | Clear message: "Nothing was saved; your text is still here" | `api.test.ts` |
| A15 | Clarity | Double submissions silently created a second case | "We already have this complaint", with the same reference number | Live UI |
| A16 | Privacy copy | The OCR dialog didn't say where the photo goes | "The text is read on this device; the photo is not uploaded" | Code |

## Strengths observed (no change needed)

- Priority levels are shown as text ("High", "Medium", "Low") plus colour and a dot, not colour alone (1.4.1).
- Form errors use `role="alert"`. In the live check, the empty-complaint message was announced.
- Labels are linked properly with `htmlFor` and `useId` throughout. The accessibility-tree inspector in the pane sometimes showed placeholders instead of names; DOM checks confirmed the labels are correct.
- The loading state has `role="status"` and screen-reader text.
- `prefers-reduced-motion` is respected by the analysis progress animation: shorter stage timing, and the sweep effect is hidden. Other framer-motion transitions were not reviewed for it.
- At 375 px, the case list has no horizontal overflow and no touch targets under 24 px (2.5.8). Cases appear as cards, not a squashed table.
- The emergency number 112 is shown on the sign-in and filing pages.
- Citizens are not shown model predictions, which avoids implying a legal determination.

## Open issues (ranked by impact)

1. **Notifications (high impact on citizens).** Status changes are not sent to complainants. They must keep checking the site.
2. **Language and literacy (high).** The interface is English only, with dense legal vocabulary (FIR, BNSS, cognizable). Multilingual support was out of scope by request. A glossary or tooltips for legal terms would help even in English.
3. **Admin portal gaps (medium).** There is no UI for:
   - routing, unit and station configuration;
   - capacity and availability editing;
   - identity recovery;
   - a cross-case audit log.

   All of them exist only as API calls or seed SQL.
4. **Length limits disagree (medium).** The complaint field caps input at 2,000 characters ("0 / 2000") while the API accepts 20,000. A detailed account can be cut short by the UI.
5. **Search field squeezed (low).** At a pane width of about 800 px, the case-list search shrinks until its placeholder reads "Search c".
6. **Hash-based URLs (low).** `#/cases/15`-style URLs look unpolished and are awkward to share. `BrowserRouter` needs a server-side fallback.
7. **Lint warnings (low).** Four `set-state-in-effect` warnings remain in loading patterns. They have no user-visible effect.
8. **Not tested:**
   - real screen readers;
   - 200% zoom and text-spacing overrides;
   - Firefox, Safari and Edge;
   - 768 px and 1920 px viewports;
   - Windows High Contrast mode.

   The result view after analysis was not seen in this session's final check, because the hidden pane stopped rendering frames.

## Recommended next steps (by impact)

1. Send SMS/email status notifications, using the existing OTP delivery code.
2. Raise the complaint field limit to match the API, or explain the limit and offer an attachment.
3. Build admin screens for capacity and availability, phone recovery, and an audit-log viewer.
4. Do a screen-reader pass with VoiceOver and NVDA on the three primary workflows, plus a 200% zoom check.
5. Add a plain-language glossary for legal terms, and Hindi or Tamil versions when multilingual support is in scope.

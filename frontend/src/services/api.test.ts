import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

async function liveApi() {
  vi.resetModules();
  vi.stubEnv("VITE_API_BASE_URL", "http://api.test");
  return import("./api");
}

describe("live mode never substitutes demo data", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new TypeError("Failed to fetch"))));
  });
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("reports an unreachable backend instead of inventing a filed complaint", async () => {
    const api = await liveApi();
    expect(api.isDemoMode()).toBe(false);
    await expect(api.classifyComplaint("Someone stole my bicycle from the library stand.")).rejects.toThrow(
      /unreachable. Nothing was saved/
    );
  });

  it("does not show synthetic cases when the case list cannot be loaded", async () => {
    const api = await liveApi();
    await expect(api.fetchCases("all", "all", "all")).rejects.toThrow();
  });

  it("passes server validation messages through", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(new Response(JSON.stringify({ error: "complaint_text must be at least 15 characters" }), { status: 400 }))
      )
    );
    const api = await liveApi();
    await expect(api.classifyComplaint("too short")).rejects.toThrow("complaint_text must be at least 15 characters");
  });
});

describe("same-origin API (VITE_API_BASE_URL=/)", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("is live mode and calls relative /api paths", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(new Response(JSON.stringify({ complaints: [] }), { status: 200 })));
    vi.stubGlobal("fetch", fetchMock);
    vi.resetModules();
    vi.stubEnv("VITE_API_BASE_URL", "/");
    const api = await import("./api");
    expect(api.isDemoMode()).toBe(false);
    await api.fetchCases("all", "all", "all");
    expect((fetchMock.mock.calls[0] as unknown as [string])[0]).toMatch(/^\/api\/complaints\?/);
  });
});

describe("demo mode", () => {
  afterEach(() => vi.unstubAllEnvs());

  it("is used only when no backend is configured", async () => {
    vi.resetModules();
    vi.stubEnv("VITE_API_BASE_URL", "");
    const api = await import("./api");
    expect(api.isDemoMode()).toBe(true);
  });
});

describe("timestamps", () => {
  it("treats backend UTC timestamps as UTC", async () => {
    const { toIsoUtc } = await import("./api");
    expect(toIsoUtc("2026-10-05 09:30:00")).toBe("2026-10-05T09:30:00Z");
    expect(toIsoUtc(null)).toBeNull();
  });
});

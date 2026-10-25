import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

async function liveApi() {
  vi.resetModules();
  vi.stubEnv("VITE_API_BASE_URL", "http://api.test");
  return import("./api");
}

function jsonOnce(body: unknown, status = 200) {
  const fetchMock = vi.fn(() => Promise.resolve(new Response(JSON.stringify(body), { status })));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

/** The URL and init a mocked fetch was called with. */
function callOf(fetchMock: ReturnType<typeof vi.fn>, index = 0) {
  const [url, init] = fetchMock.mock.calls[index] as [string, RequestInit | undefined];
  return { url, init, body: init?.body ? JSON.parse(String(init.body)) : undefined };
}

describe("decision policy reaches the administrator endpoints", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("reads severity weights from the server, not from demo data", async () => {
    const fetchMock = jsonOnce({ sections: [{ code: "302", title: "Murder", severity_weight: 10 }] });
    const api = await liveApi();
    const sections = await api.fetchSections();

    expect(callOf(fetchMock).url).toContain("/api/admin/sections");
    expect(sections).toHaveLength(1);
    expect(sections[0].code).toBe("302");
  });

  it("sends a severity change as a PATCH on that section", async () => {
    const fetchMock = jsonOnce({ section: { code: "379", title: "Theft", severity_weight: 8 } });
    const api = await liveApi();
    const updated = await api.updateSection("379", { severity_weight: 8 });

    const call = callOf(fetchMock);
    expect(call.url).toContain("/api/admin/sections/379");
    expect(call.init?.method).toBe("PATCH");
    expect(call.body).toEqual({ severity_weight: 8 });
    expect(updated.severity_weight).toBe(8);
  });

  it("surfaces the server's rejection rather than applying the change locally", async () => {
    jsonOnce({ error: "Severity weight must be a number between 1 and 10." }, 400);
    const api = await liveApi();
    await expect(api.updateSection("379", { severity_weight: 99 })).rejects.toThrow(/between 1 and 10/);
  });

  it("creates a routing rule with the section, unit and precedence", async () => {
    const fetchMock = jsonOnce(
      { rule: { id: 9, section_code: "379", unit: "Cyber Cell", precedence: 4 }, officers_available: 0 },
      201
    );
    const api = await liveApi();
    const result = await api.createRoutingRule({ section_code: "379", unit: "Cyber Cell", precedence: 4 });

    const call = callOf(fetchMock);
    expect(call.url).toContain("/api/admin/routing-rules");
    expect(call.init?.method).toBe("POST");
    expect(call.body).toEqual({ section_code: "379", unit: "Cyber Cell", precedence: 4 });
    // The count matters: a unit nobody staffs leaves cases unassigned.
    expect(result.officers_available).toBe(0);
  });

  it("deletes a routing rule by id", async () => {
    const fetchMock = jsonOnce({ deleted: 9 });
    const api = await liveApi();
    await api.deleteRoutingRule(9);

    const call = callOf(fetchMock);
    expect(call.url).toContain("/api/admin/routing-rules/9");
    expect(call.init?.method).toBe("DELETE");
  });

  it("passes a duplicate-rule conflict through instead of swallowing it", async () => {
    jsonOnce({ error: "That section already routes to that unit." }, 409);
    const api = await liveApi();
    await expect(
      api.createRoutingRule({ section_code: "379", unit: "Cyber Cell", precedence: 4 })
    ).rejects.toThrow(/already routes/);
  });
});

describe("officer availability", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("sends the new availability and returns the refreshed user", async () => {
    const fetchMock = jsonOnce({
      user: { id: 2, name: "Arjun Rao", role: "officer", unit: null, email: null, phone: null, availability: "busy" },
      cases_moved: 0,
    });
    const api = await liveApi();
    const result = await api.setAvailability("busy");

    const call = callOf(fetchMock);
    expect(call.url).toContain("/api/me/availability");
    expect(call.init?.method).toBe("PATCH");
    expect(call.body).toEqual({ availability: "busy" });
    expect(result.user.availability).toBe("busy");
  });

  it("reports how many cases moved when an officer goes on leave", async () => {
    jsonOnce({
      user: { id: 2, name: "Arjun Rao", role: "officer", unit: null, email: null, phone: null, availability: "on_leave" },
      cases_moved: 3,
    });
    const api = await liveApi();
    const result = await api.setAvailability("on_leave");
    expect(result.cases_moved).toBe(3);
  });
});

describe("staff accounts carry the fields allocation depends on", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("sends username, station and capacity when creating an officer", async () => {
    const fetchMock = jsonOnce({ user: { id: 7 }, cases_assigned: 0 }, 201);
    const api = await liveApi();
    await api.createStaff({
      name: "Meena Pillai",
      email: "meena@example.gov.in",
      role: "officer",
      password: "Password123",
      unit: "Crime Branch",
      username: "meena.pillai",
      station: "PS-NORTH",
      capacity: 12,
    });

    expect(callOf(fetchMock).body).toMatchObject({
      username: "meena.pillai",
      station: "PS-NORTH",
      capacity: 12,
    });
  });

  it("sends a station or capacity correction as a PATCH", async () => {
    const fetchMock = jsonOnce({ user: { id: 7 }, cases_moved: 0 });
    const api = await liveApi();
    await api.updateStaff(7, { station: "PS-EAST", capacity: 6 });

    const call = callOf(fetchMock);
    expect(call.url).toContain("/api/admin/users/7");
    expect(call.init?.method).toBe("PATCH");
    expect(call.body).toEqual({ station: "PS-EAST", capacity: 6 });
  });

  it("sends a password reset without echoing it back", async () => {
    const fetchMock = jsonOnce({ user: { id: 7 }, cases_moved: 0 });
    const api = await liveApi();
    const result = await api.updateStaff(7, { password: "NewPassword123" });

    expect(callOf(fetchMock).body).toEqual({ password: "NewPassword123" });
    expect(JSON.stringify(result)).not.toContain("NewPassword123");
  });
});

describe("OCR assets are served from this origin", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  it("never points tesseract.js at a CDN", async () => {
    const { OCR_ASSETS } = await import("./ocr");
    for (const path of [OCR_ASSETS.workerPath, OCR_ASSETS.corePath, OCR_ASSETS.langPath]) {
      expect(path).not.toMatch(/^https?:\/\//);
      expect(path).toContain("tesseract");
    }
  });
});

describe("stations and units administration", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("lists stations with what still depends on them", async () => {
    const fetchMock = jsonOnce({
      stations: [{ code: "PS-NORTH", name: "North", district: "Vellore", officers: 2, complaints: 4 }],
    });
    const api = await liveApi();
    const stations = await api.fetchAdminStations();

    expect(callOf(fetchMock).url).toContain("/api/admin/stations");
    expect(stations[0].officers).toBe(2);
    expect(stations[0].complaints).toBe(4);
  });

  it("refuses to hide a server rejection when a station is still in use", async () => {
    jsonOnce(
      { error: "North is still in use by 2 officer(s) and 4 complaint(s). Move them first." },
      409
    );
    const api = await liveApi();
    await expect(api.deleteStation("PS-NORTH")).rejects.toThrow(/still in use/);
  });

  it("creates a station with its code, name and district", async () => {
    const fetchMock = jsonOnce({ station: { code: "PS-WEST", name: "West", district: "Vellore" } }, 201);
    const api = await liveApi();
    await api.createStation({ code: "PS-WEST", name: "West", district: "Vellore" });

    const call = callOf(fetchMock);
    expect(call.init?.method).toBe("POST");
    expect(call.body).toEqual({ code: "PS-WEST", name: "West", district: "Vellore" });
  });

  it("reports how much a unit rename carried with it", async () => {
    const fetchMock = jsonOnce({
      unit: { name: "Anti-Narcotics Cell", description: null, registered: true, is_default: false, officers: 1, rules: 1 },
      officers_moved: 1,
      rules_moved: 1,
    });
    const api = await liveApi();
    const result = await api.updateUnit("Narcotics Cell", { name: "Anti-Narcotics Cell" });

    expect(callOf(fetchMock).url).toContain("/api/admin/units/Narcotics%20Cell");
    expect(result.officers_moved).toBe(1);
    expect(result.rules_moved).toBe(1);
  });

  it("passes through the refusal to delete the fallback unit", async () => {
    jsonOnce(
      { error: "Local Police Station is the fallback every unmatched complaint routes to and cannot be removed." },
      400
    );
    const api = await liveApi();
    await expect(api.deleteUnit("Local Police Station")).rejects.toThrow(/fallback/);
  });
});

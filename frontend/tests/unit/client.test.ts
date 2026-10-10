import { afterEach, describe, expect, it, vi } from "vitest";

import { api, ApiError, request } from "../../src/api/client";

function mockFetch(status: number, body: unknown, headers: Record<string, string> = {}) {
  return vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValue(new Response(body === undefined ? null : JSON.stringify(body), { status, headers }));
}

describe("API client error mapping", () => {
  afterEach(() => vi.restoreAllMocks());

  it("maps the backend error shape to ApiError", async () => {
    mockFetch(422, {
      error: { code: "INPUT_TOO_LONG", message: "Your code has 512 lines.", details: { line_count: 512 } },
    });
    const err = await request<never>("/api/analyses").catch((e: ApiError) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(422);
    expect(err.code).toBe("INPUT_TOO_LONG");
    expect(err.message).toBe("Your code has 512 lines.");
    expect(err.details).toEqual({ line_count: 512 });
  });

  it("reads Retry-After for rate limits", async () => {
    mockFetch(429, { error: { code: "RATE_LIMITED", message: "Too many" } }, { "Retry-After": "120" });
    const err = await request<never>("/api/analyses").catch((e: ApiError) => e);
    expect(err.code).toBe("RATE_LIMITED");
    expect(err.retryAfter).toBe(120);
  });

  it("handles non-JSON error bodies", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("<html>bad gateway</html>", { status: 502 }),
    );
    const err = await request<never>("/api/x").catch((e: ApiError) => e);
    expect(err.code).toBe("HTTP_502");
  });

  it("network failure becomes NETWORK_ERROR", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Failed to fetch"));
    const err = await request<never>("/api/x").catch((e: ApiError) => e);
    expect(err.code).toBe("NETWORK_ERROR");
  });

  it("sends JSON with credentials and returns parsed data", async () => {
    const spy = mockFetch(202, { public_id: "abc", status: "queued" });
    const res = await api.createAnalysis({ code: "x = 1", language: "python" });
    expect(res.public_id).toBe("abc");
    const [, init] = spy.mock.calls[0];
    expect(init?.credentials).toBe("include");
    expect((init?.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
    expect(JSON.parse(init?.body as string)).toEqual({ code: "x = 1", language: "python" });
  });

  it("204 returns undefined", async () => {
    mockFetch(204, undefined);
    await expect(api.logout()).resolves.toBeUndefined();
  });
});

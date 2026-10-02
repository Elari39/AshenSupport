import { afterEach, describe, it, expect, vi } from "vitest";
import { api, ApiError, setCsrf } from "./client";
afterEach(() => vi.unstubAllGlobals());
describe("API boundary", () => {
  it("sends CSRF for mutations and preserves structured failures", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValue({
        ok: false,
        status: 409,
        json: async () => ({
          error: { code: "stale_draft", message: "草稿已更新" },
        }),
      });
    vi.stubGlobal("fetch", fetch);
    setCsrf("csrf-test");
    await expect(
      api("/ticket-drafts/a/decision", "POST", { version: 1 }),
    ).rejects.toBeInstanceOf(ApiError);
    expect(fetch.mock.calls[0][1].headers["X-CSRF-Token"]).toBe("csrf-test");
  });
  it("lets the browser choose multipart boundaries", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValue({ ok: true, json: async () => ({}) });
    vi.stubGlobal("fetch", fetch);
    await api("/admin/documents", "POST", new FormData());
    expect(fetch.mock.calls[0][1].headers["Content-Type"]).toBeUndefined();
  });
});

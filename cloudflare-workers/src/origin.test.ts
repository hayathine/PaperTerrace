import { describe, it, expect, vi } from "vitest";
import worker from "./index";

describe("Origin Validation", () => {
  const env = {
    BACKEND_TUNNEL_URL: "https://backend.local",
    ALLOWED_ORIGINS:
      "https://paperterrace.pages.dev,https://www.paperterrace.page,https://paperterrace.page,http://localhost:5173",
    RATE_LIMIT_REQUESTS: "100",
    RATE_LIMIT_WINDOW: "60",
    FIREBASE_PROJECT_ID: "test-project",
    RATE_LIMIT: {
      get: vi.fn().mockResolvedValue(null),
      put: vi.fn(),
      getWithMetadata: vi.fn(),
    },
  };

  it("should allow exact allowed origin", async () => {
    const request = new Request("https://api.paperterrace.page/api/health", {
      headers: { Origin: "https://paperterrace.page" },
    });
    const response = await worker.fetch(request, env as any, {} as any);
    // It should NOT be 403. It will be 401 (Unauthorized) because of missing token, which is fine for this test.
    expect(response.status).not.toBe(403);
  });

  it("should allow origin with trailing slash if startsWith is used", async () => {
    const request = new Request("https://api.paperterrace.page/api/health", {
      headers: { Origin: "https://paperterrace.page/" },
    });
    const response = await worker.fetch(request, env as any, {} as any);
    expect(response.status).not.toBe(403);
  });

  it("should ALLOW if Origin and Referer are missing on GET (direct browser hit)", async () => {
    const request = new Request("https://api.paperterrace.page/api/health", {
      method: "GET",
      headers: {}, // No Origin, No Referer
    });
    const response = await worker.fetch(request, env as any, {} as any);
    // Should pass origin check and hit 401 Unauthorized (missing token)
    expect(response.status).toBe(401);
  });

  it("should FORBID if Origin is missing on POST", async () => {
    const request = new Request("https://api.paperterrace.page/api/health", {
      method: "POST",
      headers: {}, // No Origin, No Referer
    });
    const response = await worker.fetch(request, env as any, {} as any);
    expect(response.status).toBe(403);
    const body = await response.json();
    expect(body.message).toBe("Origin not allowed");
  });

  it("should allow if Referer is from allowed origin", async () => {
    const request = new Request("https://api.paperterrace.page/api/health", {
      headers: { Referer: "https://paperterrace.page/dashboard" },
    });
    const response = await worker.fetch(request, env as any, {} as any);
    expect(response.status).not.toBe(403);
  });
});

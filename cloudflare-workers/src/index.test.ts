import { describe, it, expect, vi, beforeEach } from "vitest";
import worker from "./index";

describe("API Gateway Worker", () => {
  const env = {
    BACKEND_TUNNEL_URL: "https://backend.local",
    ALLOWED_ORIGINS: "http://localhost:5173,https://paperterrace.page",
    RATE_LIMIT_REQUESTS: "100",
    RATE_LIMIT_WINDOW: "60",
    FIREBASE_PROJECT_ID: "test-project",
    RATE_LIMIT: {
      get: vi.fn(),
      put: vi.fn(),
      getWithMetadata: vi.fn(),
    },
  };

  beforeEach(() => {
    vi.resetAllMocks();
    // Mock global fetch for forwardRequest
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    ) as any;
  });

  it("should return 403 if origin is not allowed", async () => {
    const request = new Request("https://api.paperterrace.page/api/health", {
      headers: { Origin: "https://evil.com" },
    });

    const response = await worker.fetch(request, env as any, {} as any);
    expect(response.status).toBe(403);
  });

  it("should ALLOW guest access if Authorization header is missing", async () => {
    const request = new Request("https://api.paperterrace.page/api/health", {
      headers: {
        Origin: "https://paperterrace.page",
        "CF-Connecting-IP": "127.0.0.1",
      },
    });

    // Mock rate limit
    env.RATE_LIMIT.get.mockResolvedValue(null);

    const response = await worker.fetch(request, env as any, {} as any);

    // Should NOT be 401 anymore
    expect(response.status).toBe(200);

    // Verify backend received the guest ID
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("https://backend.local"),
      expect.objectContaining({
        headers: expect.any(Headers),
      }),
    );

    const callArgs = (global.fetch as any).mock.calls[0][1];
    expect(callArgs.headers.get("X-User-ID")).toBe("guest_127.0.0.1");
  });
});

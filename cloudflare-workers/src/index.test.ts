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
  });

  it("should return 403 if origin is not allowed", async () => {
    const request = new Request("https://api.paperterrace.page/api/health", {
      headers: { Origin: "https://evil.com" },
    });

    const response = await worker.fetch(request, env as any, {} as any);
    expect(response.status).toBe(403);
    const body = await response.json();
    expect(body.error).toBe("Forbidden");
  });

  it("should return 401 if Authorization header is missing", async () => {
    const request = new Request("https://api.paperterrace.page/api/health", {
      headers: { Origin: "https://paperterrace.page" },
    });

    // Mock rate limit
    env.RATE_LIMIT.get.mockResolvedValue(null);

    const response = await worker.fetch(request, env as any, {} as any);
    expect(response.status).toBe(401);
  });

  // Note: Complex token verification tests would require mocking global fetch or JWKS
});

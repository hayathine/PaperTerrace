import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

describe("Config Resolution", () => {
	const originalEnv = import.meta.env;
	const originalWindow = global.window;

	beforeEach(() => {
		vi.resetModules();
		vi.clearAllMocks();
	});

	afterEach(() => {
		// @ts-expect-error - import.meta.env is read-only in standard TS but we need to reset it in tests
		import.meta.env = originalEnv;
		global.window = originalWindow;
	});

	it("returns empty string in development mode (standard behavior)", async () => {
		vi.stubEnv("PROD", false);
		const { API_URL } = await import("./config");
		expect(API_URL).toBe("");
	});

	it("returns production worker URL by default in PROD", async () => {
		vi.stubEnv("PROD", true);
		vi.stubGlobal("location", { hostname: "paperterrace.pages.dev" });

		const { API_URL } = await import("./config");
		expect(API_URL).toBe("https://worker.paperterrace.page");
	});

	it("returns dev worker URL for non-production pages.dev hostname", async () => {
		vi.stubEnv("PROD", true);
		vi.stubGlobal("location", { hostname: "my-feature-branch.pages.dev" });

		const { API_URL } = await import("./config");
		expect(API_URL).toBe(
			"https://paperterracestagingworker.gwsgsgdas.workers.dev",
		);
	});

	it("returns dev worker URL for dev prefix", async () => {
		vi.stubEnv("PROD", true);
		vi.stubGlobal("location", { hostname: "dev.paperterrace.page" });

		const { API_URL } = await import("./config");
		expect(API_URL).toBe(
			"https://paperterracestagingworker.gwsgsgdas.workers.dev",
		);
	});

	it("respects VITE_API_URL if provided in PROD", async () => {
		vi.stubEnv("PROD", true);
		vi.stubEnv("VITE_API_URL", "https://custom-api.com");
		// Ensure hostname doesn't trigger dev logic
		vi.stubGlobal("location", { hostname: "paperterrace.pages.dev" });

		const { API_URL } = await import("./config");
		expect(API_URL).toBe("https://custom-api.com");
	});
});

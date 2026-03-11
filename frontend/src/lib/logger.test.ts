import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { API_URL } from "@/config";
import { createLogger } from "./logger";

// Mock Sentry
vi.mock("@sentry/react", () => ({
	withScope: vi.fn((callback) => {
		const scope = {
			setTag: vi.fn(),
			setExtra: vi.fn(),
		};
		callback(scope);
	}),
	captureException: vi.fn(),
	captureMessage: vi.fn(),
}));

describe("Logger Utility", () => {
	const componentName = "TestComponent";
	let consoleSpy: Record<string, any>;

	beforeEach(() => {
		vi.clearAllMocks();
		consoleSpy = {
			debug: vi.spyOn(console, "debug").mockImplementation(() => {}),
			info: vi.spyOn(console, "info").mockImplementation(() => {}),
			warn: vi.spyOn(console, "warn").mockImplementation(() => {}),
			error: vi.spyOn(console, "error").mockImplementation(() => {}),
		};

		// Mock fetch for error reporting
		vi.stubGlobal(
			"fetch",
			vi.fn(() => Promise.resolve({ ok: true })),
		);
	});

	afterEach(() => {
		vi.restoreAllMocks();
	});

	it("should log debug messages in development", () => {
		const logger = createLogger(componentName);
		logger.debug("op", "msg");
		expect(consoleSpy.debug).toHaveBeenCalledWith(
			`[${componentName}.op]`,
			"msg",
		);
	});

	it("should include context in console logs", () => {
		const logger = createLogger(componentName);
		const context = { foo: "bar" };
		logger.info("op", "msg", context);
		expect(consoleSpy.info).toHaveBeenCalledWith(
			`[${componentName}.op]`,
			"msg",
			context,
		);
	});

	it("should report errors to server and Sentry", async () => {
		const logger = createLogger(componentName);
		const error = new Error("Test Error");
		const context = { error };

		logger.error("op", "msg", context);

		expect(consoleSpy.error).toHaveBeenCalled();

		// Verify server reporting
		expect(global.fetch).toHaveBeenCalledWith(
			`${API_URL}/api/client-errors`,
			expect.objectContaining({
				method: "POST",
				body: expect.stringContaining("Test Error"),
			}),
		);

		// Wait for the dynamic import and the .then() callback
		await new Promise((resolve) => setTimeout(resolve, 10));

		const Sentry = await import("@sentry/react");
		expect(Sentry.captureException).toHaveBeenCalledWith(error);
	});

	it("should use captureMessage when no Error object is provided to error logger", async () => {
		const logger = createLogger(componentName);
		logger.error("op", "msg");

		await new Promise((resolve) => setTimeout(resolve, 10));

		const Sentry = await import("@sentry/react");
		expect(Sentry.captureMessage).toHaveBeenCalledWith("msg", "error");
	});
});

import { beforeEach, describe, expect, it, vi } from "vitest";
import { performanceMonitor } from "./performance";

// Mock web-vitals
vi.mock("web-vitals", () => ({
	onCLS: vi.fn(),
	onFCP: vi.fn(),
	onLCP: vi.fn(),
	onTTFB: vi.fn(),
}));

const mockConfig = vi.hoisted(() => ({
	performanceMonitoring: true,
}));

// Mock config
vi.mock("../config/performance", () => ({
	PERF_FLAGS: mockConfig,
}));

import { onCLS, onFCP, onLCP, onTTFB } from "web-vitals";

describe("PerformanceMonitor", () => {
	beforeEach(() => {
		vi.clearAllMocks();
		mockConfig.performanceMonitoring = true;
	});

	it("should initialize and register web-vitals handlers when enabled", () => {
		performanceMonitor.init();

		expect(onCLS).toHaveBeenCalled();
		expect(onFCP).toHaveBeenCalled();
		expect(onLCP).toHaveBeenCalled();
		expect(onTTFB).toHaveBeenCalled();
	});

	it("should not register handlers when disabled", () => {
		mockConfig.performanceMonitoring = false;
		performanceMonitor.init();

		// Check that handlers were NOT called again
		// Note: since it's a singleton, it might have been called in previous test.
		// But clearAllMocks() was called in beforeEach.
		expect(onCLS).not.toHaveBeenCalled();
	});

	it("should store metrics correctly when handlers are called", () => {
		performanceMonitor.init();

		// Get the handler passed to onFCP
		const handler = (onFCP as any).mock.calls[0][0];

		const mockMetric = {
			name: "FCP",
			value: 1200,
			rating: "good",
			delta: 1200,
			entries: [],
			id: "v3-123",
		};

		handler(mockMetric);

		const metrics = performanceMonitor.getMetrics();
		expect(metrics).toHaveLength(1);
		expect(metrics[0].name).toBe("FCP");
		expect(metrics[0].value).toBe(1200);
		expect(metrics[0].rating).toBe("good");
	});
});

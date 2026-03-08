import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useServiceHealth } from "./useServiceHealth";

describe("useServiceHealth", () => {
	beforeEach(() => {
		vi.stubGlobal("fetch", vi.fn());
	});

	afterEach(() => {
		vi.restoreAllMocks();
		vi.useRealTimers();
	});

	it("should start with healthy status", () => {
		const { result } = renderHook(() => useServiceHealth(false));
		expect(result.current.isHealthy).toBe(true);
		expect(result.current.status).toBe("healthy");
	});

	it("should fetch health status on mount if enabled", async () => {
		(fetch as any).mockResolvedValue({
			status: 200,
			json: async () => ({ status: "healthy" }),
		});

		renderHook(() => useServiceHealth(true));

		await waitFor(() => {
			expect(fetch).toHaveBeenCalled();
		});
	});

	it("should become unhealthy if fetch fails", async () => {
		(fetch as any).mockRejectedValue(new Error("Network error"));

		const { result } = renderHook(() => useServiceHealth(true));

		await waitFor(() => {
			expect(result.current.isUnhealthy).toBe(true);
		});
		expect(result.current.status).toBe("unhealthy");
	});

	it("should handle maintenance status (503)", async () => {
		(fetch as any).mockResolvedValue({
			status: 503,
			json: async () => ({ status: "maintenance", message: "Back soon!" }),
		});

		const { result } = renderHook(() => useServiceHealth(true));

		await waitFor(() => {
			expect(result.current.isMaintenance).toBe(true);
		});
		expect(result.current.status).toBe("maintenance");
		expect(result.current.message).toBe("Back soon!");
	});

	it("should trigger immediate health check on reportFailure(503)", async () => {
		(fetch as any).mockResolvedValue({
			status: 200,
			json: async () => ({ status: "healthy" }),
		});

		const { result } = renderHook(() => useServiceHealth(true));

		// Wait for initial check
		await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));

		// Call reportFailure
		await act(async () => {
			result.current.reportFailure(503);
		});

		expect(fetch).toHaveBeenCalledTimes(2);
	});

	it("should poll when unhealthy", async () => {
		vi.useFakeTimers();

		(fetch as any).mockResolvedValue({
			status: 500,
			json: async () => ({}),
		});

		const { result } = renderHook(() => useServiceHealth(true));

		// Advance to complete the initial async fetch
		await act(async () => {
			await vi.advanceTimersByTimeAsync(0);
		});

		expect(result.current.isUnhealthy).toBe(true);

		// Next fetch succeeds
		(fetch as any).mockResolvedValue({
			status: 200,
			json: async () => ({ status: "healthy" }),
		});

		// Advance timers by POLL_INTERVAL_UNHEALTHY (10000ms)
		await act(async () => {
			await vi.advanceTimersByTimeAsync(10000);
		});

		expect(result.current.isHealthy).toBe(true);
	});
});

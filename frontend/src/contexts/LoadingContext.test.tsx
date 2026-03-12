import { act, renderHook } from "@testing-library/react";
import type React from "react";
import { describe, expect, it } from "vitest";
import { LoadingProvider, useLoading } from "./LoadingContext";

describe("LoadingContext", () => {
	it("should provide default values", () => {
		const wrapper = ({ children }: { children: React.ReactNode }) => (
			<LoadingProvider>{children}</LoadingProvider>
		);
		const { result } = renderHook(() => useLoading(), { wrapper });

		expect(result.current.isLoading).toBe(false);
		expect(result.current.message).toBe(null);
	});

	it("should start and stop loading", () => {
		const wrapper = ({ children }: { children: React.ReactNode }) => (
			<LoadingProvider>{children}</LoadingProvider>
		);
		const { result } = renderHook(() => useLoading(), { wrapper });

		act(() => {
			result.current.startLoading("Testing...");
		});
		expect(result.current.isLoading).toBe(true);
		expect(result.current.message).toBe("Testing...");

		act(() => {
			result.current.stopLoading();
		});
		expect(result.current.isLoading).toBe(false);
		expect(result.current.message).toBe(null);
	});

	it("should throw error if used outside provider", () => {
		// Suppress console.error for this test as it's expected to throw
		const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

		expect(() => renderHook(() => useLoading())).toThrow(
			"useLoading must be used within a LoadingProvider",
		);

		consoleSpy.mockRestore();
	});
});

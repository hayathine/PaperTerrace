import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi } from "vitest";
import GlobalLoading from "./GlobalLoading";

// Mock the hooks
vi.mock("react-i18next", () => ({
	useTranslation: () => ({
		t: (key: string) => (key === "common.preparing" ? "Preparing..." : key),
	}),
}));

const mockUseLoading = vi.fn();

vi.mock("../../contexts/LoadingContext", () => ({
	useLoading: () => mockUseLoading(),
}));

describe("GlobalLoading Component", () => {
	it("renders null when not loading", () => {
		mockUseLoading.mockReturnValue({
			isLoading: false,
			message: null,
		});
		const { container } = render(<GlobalLoading />);
		expect(container.firstChild).toBeNull();
	});

	it("renders loading message when provided", () => {
		mockUseLoading.mockReturnValue({
			isLoading: true,
			message: "Processing data...",
		});
		render(<GlobalLoading />);
		expect(screen.getByText("Processing data...")).toBeDefined();
	});

	it("renders default translation message when no custom message provided", () => {
		mockUseLoading.mockReturnValue({
			isLoading: true,
			message: null,
		});
		render(<GlobalLoading />);
		// Based on our mock t, it should return "Preparing..." for "common.preparing"
		expect(screen.getByText("Preparing...")).toBeDefined();
	});
});

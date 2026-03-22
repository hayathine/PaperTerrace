import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ErrorBoundary from "./ErrorBoundary";

describe("ErrorBoundary", () => {
	const originalLocation = window.location;

	beforeEach(() => {
		vi.clearAllMocks();
		// Mock window.location.reload
		Object.defineProperty(window, "location", {
			configurable: true,
			value: { reload: vi.fn() },
		});
	});

	afterEach(() => {
		Object.defineProperty(window, "location", {
			configurable: true,
			value: originalLocation,
		});
	});

	it("renders children when no error occurs", () => {
		render(
			<ErrorBoundary>
				<div data-testid="child">Success</div>
			</ErrorBoundary>,
		);
		expect(screen.getByTestId("child")).toBeDefined();
		expect(screen.queryByText("common.error_boundary.title")).toBeNull();
	});

	it("renders fallback UI when an error occurs in children", () => {
		const ProblematicComponent = () => {
			throw new Error("Test Error");
		};

		// Prevent console.error from cluttering test output
		const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

		render(
			<ErrorBoundary>
				<ProblematicComponent />
			</ErrorBoundary>,
		);

		expect(screen.getByText("common.error_boundary.title")).toBeDefined();
		expect(screen.queryByTestId("child")).toBeNull();

		consoleSpy.mockRestore();
	});

	it("reloads the page when the reload button is clicked", () => {
		const ProblematicComponent = () => {
			throw new Error("Test Error");
		};
		vi.spyOn(console, "error").mockImplementation(() => {});

		render(
			<ErrorBoundary>
				<ProblematicComponent />
			</ErrorBoundary>,
		);

		const reloadButton = screen.getByText("common.error_boundary.reload");
		fireEvent.click(reloadButton);

		expect(window.location.reload).toHaveBeenCalledTimes(1);
	});
});

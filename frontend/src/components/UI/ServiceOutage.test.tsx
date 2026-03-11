import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ServiceOutage from "./ServiceOutage";

// Mock i18next
vi.mock("react-i18next", () => ({
	useTranslation: () => ({
		t: (key: string, defaultValue?: string) => defaultValue || key,
	}),
}));

describe("ServiceOutage Component", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("renders standard outage message by default (isMaintenance=false)", () => {
		render(<ServiceOutage isMaintenance={false} />);

		expect(
			screen.getByText("Service Temporarily Unavailable"),
		).toBeInTheDocument();
		expect(
			screen.getByText(
				"Our servers are currently over capacity. Please try again in a few minutes.",
			),
		).toBeInTheDocument();
	});

	it("renders maintenance message when isMaintenance is true", () => {
		render(<ServiceOutage isMaintenance={true} />);

		expect(screen.getByText("System Maintenance")).toBeInTheDocument();
		expect(
			screen.getByText(
				"We're currently performing some improvements. We'll be back shortly.",
			),
		).toBeInTheDocument();
	});

	it("renders custom message if provided", () => {
		const customMsg = "Custom error message here";
		render(<ServiceOutage message={customMsg} />);

		expect(screen.getByText(customMsg)).toBeInTheDocument();
	});

	it("calls window.location.reload when retry button is clicked", () => {
		// Mock window.location.reload
		const reloadSpy = vi.fn();
		vi.stubGlobal("location", { ...window.location, reload: reloadSpy });

		render(<ServiceOutage />);
		const retryButton = screen.getByText("Retry Connection");
		fireEvent.click(retryButton);

		expect(reloadSpy).toHaveBeenCalled();
	});
});

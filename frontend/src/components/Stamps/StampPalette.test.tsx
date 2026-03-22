import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { API_URL } from "@/config";
import StampPalette from "./StampPalette";

describe("StampPalette Component", () => {
	const onToggleModeMock = vi.fn();
	const onSelectStampMock = vi.fn();
	const selectedStamp = "👍";

	beforeEach(() => {
		vi.clearAllMocks();
		localStorage.clear();
		// Mock fetch for custom stamp upload
		vi.stubGlobal(
			"fetch",
			vi.fn(() =>
				Promise.resolve({
					ok: true,
					json: () => Promise.resolve({ url: "/static/custom-stamp.jpg" }),
				}),
			),
		);
	});

	it("renders the toggle button and mode text", () => {
		render(
			<StampPalette
				isStampMode={false}
				onToggleMode={onToggleModeMock}
				selectedStamp={selectedStamp}
				onSelectStamp={onSelectStampMock}
			/>,
		);

		expect(screen.getByText("Use Stamps")).toBeInTheDocument();
	});

	it("calls onToggleMode when the main button is clicked", () => {
		render(
			<StampPalette
				isStampMode={false}
				onToggleMode={onToggleModeMock}
				selectedStamp={selectedStamp}
				onSelectStamp={onSelectStampMock}
			/>,
		);

		fireEvent.click(screen.getByText("Use Stamps"));
		expect(onToggleModeMock).toHaveBeenCalled();
	});

	it("shows the palette when isStampMode is true", () => {
		render(
			<StampPalette
				isStampMode={true}
				onToggleMode={onToggleModeMock}
				selectedStamp={selectedStamp}
				onSelectStamp={onSelectStampMock}
			/>,
		);

		expect(screen.getByText("Stamp Mode Active")).toBeInTheDocument();
		// Check if category buttons are visible
		expect(screen.getByText("Quick")).toBeInTheDocument();
		expect(screen.getByText("Reactions")).toBeInTheDocument();
	});

	it("calls onSelectStamp when a stamp icon is clicked", () => {
		render(
			<StampPalette
				isStampMode={true}
				onToggleMode={onToggleModeMock}
				selectedStamp={selectedStamp}
				onSelectStamp={onSelectStampMock}
			/>,
		);

		// Click '❤️'
		fireEvent.click(screen.getByText("❤️"));
		expect(onSelectStampMock).toHaveBeenCalledWith("❤️");
	});

	it("loads custom stamps from localStorage", () => {
		localStorage.setItem(
			"customStamps",
			JSON.stringify(["/static/old-custom.jpg"]),
		);

		render(
			<StampPalette
				isStampMode={true}
				onToggleMode={onToggleModeMock}
				selectedStamp={selectedStamp}
				onSelectStamp={onSelectStampMock}
			/>,
		);

		fireEvent.click(screen.getByText("Custom"));
		const img = screen.getByRole("img");
		expect(img).toHaveAttribute("src", `${API_URL}/static/old-custom.jpg`);
	});

	it("handles custom stamp upload", async () => {
		const { container } = render(
			<StampPalette
				isStampMode={true}
				onToggleMode={onToggleModeMock}
				selectedStamp={selectedStamp}
				onSelectStamp={onSelectStampMock}
			/>,
		);

		fireEvent.click(screen.getByText("Custom"));

		const file = new File(["(⌐□_□)"], "stamp.jpg", { type: "image/jpeg" });
		const input = container.querySelector(
			'input[type="file"]',
		) as HTMLInputElement;

		fireEvent.change(input, { target: { files: [file] } });

		await waitFor(() => {
			expect(global.fetch).toHaveBeenCalledWith(
				expect.stringContaining("/api/stamps/upload_custom"),
				expect.any(Object),
			);
		});

		expect(onSelectStampMock).toHaveBeenCalledWith("/static/custom-stamp.jpg");
		expect(localStorage.getItem("customStamps")).toContain(
			"/static/custom-stamp.jpg",
		);
	});
});

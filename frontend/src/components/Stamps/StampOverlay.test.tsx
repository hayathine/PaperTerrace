import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import StampOverlay from "./StampOverlay";

describe("StampOverlay Component", () => {
	const mockStamps = [
		{ id: "1", x: 20, y: 30, type: "👍" },
		{ id: "2", x: 50, y: 50, type: "https://example.com/stamp.png" },
	];
	const onAddStampMock = vi.fn();
	const onDeleteStampMock = vi.fn();

	beforeEach(() => {
		vi.clearAllMocks();
		vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({
			width: 1000,
			height: 1000,
			top: 0,
			left: 0,
		} as any);
	});

	it("renders stamps correctly", () => {
		render(
			<StampOverlay
				stamps={mockStamps}
				isStampMode={false}
				onAddStamp={onAddStampMock}
			/>,
		);

		expect(screen.getByText("👍")).toBeInTheDocument();
		const imageStamp = screen.getByRole("img");
		expect(imageStamp).toHaveAttribute("src", "https://example.com/stamp.png");
	});

	it("calls onAddStamp with correct coordinates when clicked in stamp mode", () => {
		render(
			<StampOverlay
				stamps={[]}
				isStampMode={true}
				onAddStamp={onAddStampMock}
			/>,
		);

		const overlay = screen.getByLabelText("Add stamp overlay");
		fireEvent.click(overlay, { clientX: 250, clientY: 400 });

		expect(onAddStampMock).toHaveBeenCalledWith(25, 40); // 250/1000 * 100
	});

	it("does not call onAddStamp when clicked and NOT in stamp mode", () => {
		render(
			<StampOverlay
				stamps={[]}
				isStampMode={false}
				onAddStamp={onAddStampMock}
			/>,
		);

		const overlay = screen.getByLabelText("Add stamp overlay");
		// Button will have pointer-events-none class, but fireEvent bypasses CSS
		// The implementation checks isStampMode specifically
		fireEvent.click(overlay, { clientX: 250, clientY: 400 });

		expect(onAddStampMock).not.toHaveBeenCalled();
	});

	it("calls onDeleteStamp when a stamp is right-clicked", () => {
		render(
			<StampOverlay
				stamps={mockStamps}
				isStampMode={true}
				onAddStamp={onAddStampMock}
				onDeleteStamp={onDeleteStampMock}
			/>,
		);

		const stamp = screen.getByText("👍");
		fireEvent.contextMenu(stamp);

		expect(onDeleteStampMock).toHaveBeenCalledWith("1");
	});
});

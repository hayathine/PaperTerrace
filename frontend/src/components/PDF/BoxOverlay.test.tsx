import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import BoxOverlay from "./BoxOverlay";

describe("BoxOverlay Component", () => {
	const onSelectMock = vi.fn();

	beforeEach(() => {
		onSelectMock.mockClear();
		// JSDOM doesn't implement getBoundingClientRect with actual dimensions
		// We mock it for the containerRef
		vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({
			width: 1000,
			height: 1000,
			top: 0,
			left: 0,
			bottom: 1000,
			right: 1000,
			x: 0,
			y: 0,
			toJSON: () => {},
		});
	});

	it("renders nothing when isActive is false", () => {
		const { container } = render(
			<BoxOverlay isActive={false} onSelect={onSelectMock} />,
		);
		expect(container.firstChild).toBeNull();
	});

	it("renders overlay when isActive is true", () => {
		render(<BoxOverlay isActive={true} onSelect={onSelectMock} />);
		const overlay = screen.getByLabelText("Selection overlay");
		expect(overlay).toBeInTheDocument();
	});

	it("triggers onSelect with correct coordinates after mouse drag", () => {
		render(<BoxOverlay isActive={true} onSelect={onSelectMock} />);
		const overlay = screen.getByLabelText("Selection overlay");

		// Start at (100, 100) -> 10%
		fireEvent.mouseDown(overlay, { clientX: 100, clientY: 100 });

		// Move to (300, 400) -> 30%, 40%
		fireEvent.mouseMove(window, { clientX: 300, clientY: 400 });

		// Finish
		fireEvent.mouseUp(window, { clientX: 300, clientY: 400 });

		// Finish
		fireEvent.mouseUp(window, { clientX: 300, clientY: 400 });

		const call = onSelectMock.mock.calls[0][0];
		expect(call.x).toBeCloseTo(0.1);
		expect(call.y).toBeCloseTo(0.1);
		expect(call.width).toBeCloseTo(0.2);
		expect(call.height).toBeCloseTo(0.3);
	});

	it("triggers onSelect with absolute values regardless of drag direction", () => {
		render(<BoxOverlay isActive={true} onSelect={onSelectMock} />);
		const overlay = screen.getByLabelText("Selection overlay");

		// Drag from bottom-right to top-left
		fireEvent.mouseDown(overlay, { clientX: 500, clientY: 500 });
		fireEvent.mouseUp(window, { clientX: 100, clientY: 100 });

		const call = onSelectMock.mock.calls[0][0];
		expect(call.x).toBeCloseTo(0.1);
		expect(call.y).toBeCloseTo(0.1);
		expect(call.width).toBeCloseTo(0.4);
		expect(call.height).toBeCloseTo(0.4);
	});

	it("does not trigger onSelect if selection is too small", () => {
		render(<BoxOverlay isActive={true} onSelect={onSelectMock} />);
		const overlay = screen.getByLabelText("Selection overlay");

		// Very small drag (less than 1% of 1000px is 10px)
		fireEvent.mouseDown(overlay, { clientX: 100, clientY: 100 });
		fireEvent.mouseUp(window, { clientX: 105, clientY: 105 }); // 5px diff = 0.5%

		expect(onSelectMock).not.toHaveBeenCalled();
	});

	it("handles touch events correctly", () => {
		render(<BoxOverlay isActive={true} onSelect={onSelectMock} />);
		const overlay = screen.getByLabelText("Selection overlay");

		// Start touch
		fireEvent.touchStart(overlay, {
			touches: [{ clientX: 200, clientY: 200 }],
		});

		// End touch
		fireEvent.touchEnd(window, {
			changedTouches: [{ clientX: 500, clientY: 500 }],
		});

		const call = onSelectMock.mock.calls[0][0];
		expect(call.x).toBeCloseTo(0.2);
		expect(call.y).toBeCloseTo(0.2);
		expect(call.width).toBeCloseTo(0.3);
		expect(call.height).toBeCloseTo(0.3);
	});
});

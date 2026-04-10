import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import UploadScreen from "./UploadScreen";

vi.mock("react-router-dom", () => ({
	useNavigate: () => vi.fn(),
}));

vi.mock("@/contexts/AuthContext", () => ({
	useAuth: () => ({ user: null, isGuest: true }),
}));

describe("UploadScreen Component", () => {
	it("renders brand section and upload message", () => {
		render(<UploadScreen onFileSelect={() => {}} />);
		expect(screen.getByText("PaperTerrace")).toBeDefined();
		expect(screen.getByText(/PDFをドロップして読み込み/)).toBeDefined();
	});

	it("triggers onFileSelect when a file is selected via input", () => {
		const onFileSelect = vi.fn();
		const { container } = render(<UploadScreen onFileSelect={onFileSelect} />);

		const input = container.querySelector(
			'input[type="file"]',
		) as HTMLInputElement;
		const file = new File(["dummy content"], "test.pdf", {
			type: "application/pdf",
		});

		fireEvent.change(input, { target: { files: [file] } });

		expect(onFileSelect).toHaveBeenCalledWith(file);
	});

	it("changes style when dragging over", () => {
		const { container } = render(<UploadScreen onFileSelect={() => {}} />);
		const dropZone = container.querySelector("button");
		if (!dropZone) throw new Error("Button not found");

		fireEvent.dragOver(dropZone);
		// Check if class change occurred (e.g. border-orange-400)
		expect(dropZone.className).toContain("border-orange-400");

		fireEvent.dragLeave(dropZone);
		expect(dropZone.className).not.toContain("border-orange-400");
	});

	it("handles drop event", () => {
		const onFileSelect = vi.fn();
		const { container } = render(<UploadScreen onFileSelect={onFileSelect} />);
		const dropZone = container.querySelector("button");
		if (!dropZone) throw new Error("Button not found");

		const file = new File(["dummy content"], "test.pdf", {
			type: "application/pdf",
		});

		// fireEvent.drop doesn't automatically populate e.dataTransfer correctly for all cases,
		// but Testing Library's fireEvent.drop accepts an object that mimics it.
		fireEvent.drop(dropZone, {
			dataTransfer: {
				files: [file],
			},
		});

		expect(onFileSelect).toHaveBeenCalledWith(file);
	});

	it("shows alert for non-pdf files on drop", () => {
		const onFileSelect = vi.fn();
		const { container } = render(<UploadScreen onFileSelect={onFileSelect} />);
		const dropZone = container.querySelector("button");
		if (!dropZone) throw new Error("Button not found");

		const file = new File(["dummy content"], "test.txt", {
			type: "text/plain",
		});

		fireEvent.drop(dropZone, {
			dataTransfer: {
				files: [file],
			},
		});

		expect(screen.getByText("common.errors.file_type_invalid")).toBeDefined();
		expect(onFileSelect).not.toHaveBeenCalled();
		expect(onFileSelect).not.toHaveBeenCalled();
	});
});

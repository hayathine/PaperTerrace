import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { API_URL } from "@/config";
import RequestForm from "./RequestForm";

// Mock i18next
vi.mock("react-i18next", () => ({
	useTranslation: () => ({
		t: (key: string) => {
			const translations: Record<string, string> = {
				"contact.title": "要望・ご意見を送る",
				"contact.placeholder": "機能要望やご意見をお気軽にどうぞ...",
				"contact.submit": "送信する",
				"contact.submitting": "送信中",
				"contact.success": "ありがとうございます！",
				"contact.retry": "もう一度",
				"contact.error": "送信に失敗しました。再試行してください。",
			};
			return translations[key] || key;
		},
	}),
}));

describe("RequestForm", () => {
	beforeEach(() => {
		vi.clearAllMocks();
		// Mock fetch
		global.fetch = vi.fn();
	});

	it("renders the form initially", () => {
		render(<RequestForm />);
		expect(screen.getByText("要望・ご意見を送る")).toBeInTheDocument();
		expect(
			screen.getByPlaceholderText("機能要望やご意見をお気軽にどうぞ..."),
		).toBeInTheDocument();
		expect(
			screen.getByRole("button", { name: /送信する/i }),
		).toBeInTheDocument();
	});

	it("submits the form successfully", async () => {
		(global.fetch as any).mockResolvedValueOnce({
			ok: true,
		});

		render(<RequestForm />);
		const textarea = screen.getByPlaceholderText(
			"機能要望やご意見をお気軽にどうぞ...",
		);
		const submitButton = screen.getByRole("button", { name: /送信する/i });

		fireEvent.change(textarea, { target: { value: "Test feedback" } });
		fireEvent.click(submitButton);

		expect(screen.getByText("送信中")).toBeInTheDocument();

		await waitFor(() => {
			expect(screen.getByText("ありがとうございます！")).toBeInTheDocument();
		});

		expect(global.fetch).toHaveBeenCalledWith(
			`${API_URL}/api/contact`,
			expect.objectContaining({
				method: "POST",
				body: JSON.stringify({ message: "Test feedback" }),
			}),
		);
	});

	it("handles server error", async () => {
		(global.fetch as any).mockResolvedValueOnce({
			ok: false,
		});

		render(<RequestForm />);
		const textarea = screen.getByPlaceholderText(
			"機能要望やご意見をお気軽にどうぞ...",
		);
		const submitButton = screen.getByRole("button", { name: /送信する/i });

		fireEvent.change(textarea, { target: { value: "Test error" } });
		fireEvent.click(submitButton);

		await waitFor(() => {
			expect(
				screen.getByText("送信に失敗しました。再試行してください。"),
			).toBeInTheDocument();
		});
	});

	it("disables submit button when message is empty", () => {
		render(<RequestForm />);
		const submitButton = screen.getByRole("button", { name: /送信する/i });
		expect(submitButton).toBeDisabled();
	});
});

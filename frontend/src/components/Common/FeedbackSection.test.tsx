import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as feedbackLib from "@/lib/feedback";
import FeedbackSection from "./FeedbackSection";

// Mock i18next
vi.mock("react-i18next", () => ({
	useTranslation: () => ({
		t: (key: string) => key,
	}),
}));

// Mock feedback library
vi.mock("@/lib/feedback", () => ({
	submitFeedback: vi.fn(),
}));

describe("FeedbackSection Component", () => {
	const props = {
		sessionId: "session-123",
		targetType: "chat" as const,
		targetId: "target-456",
		traceId: "trace-789",
	};

	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("renders feedback buttons", () => {
		render(<FeedbackSection {...props} />);
		expect(screen.getByText("common.feedback.good")).toBeDefined();
		expect(screen.getByText("common.feedback.bad")).toBeDefined();
	});

	it("submits score when clicked", async () => {
		(feedbackLib.submitFeedback as any).mockResolvedValue({ status: "ok" });
		render(<FeedbackSection {...props} />);

		const goodBtn = screen.getByText("common.feedback.good");
		fireEvent.click(goodBtn);

		expect(feedbackLib.submitFeedback).toHaveBeenCalledWith(
			expect.objectContaining({
				user_rating: 1,
				target_type: "chat",
			}),
		);

		await waitFor(() => {
			expect(screen.getByText("common.feedback.submitted")).toBeDefined();
		});
	});

	it("submits comment when send button clicked", async () => {
		(feedbackLib.submitFeedback as any).mockResolvedValue({ status: "ok" });
		render(<FeedbackSection {...props} />);

		const textarea = screen.getByPlaceholderText("common.feedback.placeholder");
		fireEvent.change(textarea, { target: { value: "Great job!" } });

		const sendBtn = screen.getByText("common.feedback.send");
		fireEvent.click(sendBtn);

		expect(feedbackLib.submitFeedback).toHaveBeenCalledWith(
			expect.objectContaining({
				user_comment: "Great job!",
				target_type: "chat",
			}),
		);
	});

	it("handles error during submission", async () => {
		(feedbackLib.submitFeedback as any).mockRejectedValue(
			new Error("Network Error"),
		);
		render(<FeedbackSection {...props} />);

		const goodBtn = screen.getByText("common.feedback.good");
		fireEvent.click(goodBtn);

		await waitFor(() => {
			expect(screen.getByText("common.error.generic")).toBeDefined();
		});
	});
});

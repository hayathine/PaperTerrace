import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useLayoutPolling } from "./useLayoutPolling";

// Better Mock EventSource
const eventSourceInstances: MockEventSource[] = [];
class MockEventSource {
	onmessage: ((ev: any) => any) | null = null;
	onerror: ((ev: any) => any) | null = null;
	close = vi.fn();
	constructor(public url: string) {
		eventSourceInstances.push(this);
	}
}
(global as any).EventSource = MockEventSource;

// Mock db available
vi.mock("../db/index", () => ({
	isDbAvailable: () => true,
}));

describe("useLayoutPolling Hook", () => {
	const setPages = vi.fn();
	const getCachedPaper = vi.fn().mockResolvedValue(null);
	const savePaperToCache = vi.fn();

	const defaultDeps = {
		token: "test-token",
		sessionId: "test-session",
		getCachedPaper,
		savePaperToCache,
		setPages,
	};

	beforeEach(() => {
		vi.clearAllMocks();
		eventSourceInstances.length = 0;
		global.fetch = vi.fn();
	});

	it("should apply layout figures correctly", () => {
		const { result } = renderHook(() => useLayoutPolling(defaultDeps));
		const figures = [{ page_num: 1, image_url: "/img1.jpg" }];

		result.current.applyLayoutFigures(figures, "paper-1", "hash-1");

		expect(setPages).toHaveBeenCalled();
		const setPagesUpdater = setPages.mock.calls[0][0];

		const prevPages = [{ page_num: 1, figures: [] }];
		const nextPages = setPagesUpdater(prevPages);

		expect(nextPages[0].figures).toHaveLength(1);
		expect(nextPages[0].figures[0].image_url).toContain("/img1.jpg");
	});

	it("should trigger lazy layout analysis and poll for results via SSE", async () => {
		const mockJob = { job_id: "job-123", stream_url: "/stream/123" };
		(global.fetch as any).mockResolvedValueOnce({
			ok: true,
			json: async () => mockJob,
		});

		const { result } = renderHook(() => useLayoutPolling(defaultDeps));
		const initialPages = [
			{ page_num: 1, image_url: "/static/paper_images/hash-1/1.jpg" },
		] as any;

		// Start analysis
		act(() => {
			result.current.triggerLazyLayoutAnalysis("paper-1", initialPages);
		});

		await waitFor(() => {
			expect(global.fetch).toHaveBeenCalledWith(
				expect.stringContaining("/api/analyze-layout-lazy"),
				expect.any(Object),
			);
			expect(eventSourceInstances).toHaveLength(1);
		});

		const es = eventSourceInstances[0];

		// Simulate SSE "completed" message
		const mockEvent = {
			data: JSON.stringify({
				status: "completed",
				figures: [{ page_num: 1, image_url: "/fig1.jpg" }],
			}),
		};

		act(() => {
			if (es.onmessage) es.onmessage(mockEvent);
		});

		expect(setPages).toHaveBeenCalled();
		expect(es.close).toHaveBeenCalled();
	});

	it("should handle job failure in SSE", async () => {
		(global.fetch as any).mockResolvedValueOnce({
			ok: true,
			json: async () => ({ job_id: "job-err", stream_url: "/stream/err" }),
		});

		const { result } = renderHook(() => useLayoutPolling(defaultDeps));
		const initialPages = [
			{ page_num: 1, image_url: "/static/paper_images/hash-1/1.jpg" },
		] as any;

		act(() => {
			result.current.triggerLazyLayoutAnalysis("paper-1", initialPages);
		});

		await waitFor(() => expect(eventSourceInstances).toHaveLength(1));
		const es = eventSourceInstances[0];

		act(() => {
			if (es.onmessage) {
				es.onmessage({
					data: JSON.stringify({ status: "failed", error: "OOM" }),
				});
			}
		});

		expect(es.close).toHaveBeenCalled();
	});
});

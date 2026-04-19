import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// Override global setup.ts AuthContext mock with controllable state
let mockUser: any = { id: "test-user", name: "Test User" };
let mockIsGuest = false;
const mockToken = "mock-token";

vi.mock("@/contexts/AuthContext", () => ({
	useAuth: () => ({
		user: mockUser,
		isGuest: mockIsGuest,
		logout: vi.fn(),
		token: mockToken,
	}),
}));

vi.mock("@/contexts/LoadingContext", () => ({
	useLoading: () => ({ startLoading: vi.fn(), stopLoading: vi.fn() }),
}));

const mockGetCachedPaper = vi.fn();
const mockDeletePaperCacheDb = vi.fn();
vi.mock("@/db/hooks", () => ({
	usePaperCache: () => ({
		getCachedPaper: mockGetCachedPaper,
		deletePaperCache: mockDeletePaperCacheDb,
	}),
}));

vi.mock("@/db/sync", () => ({
	useSyncStatus: () => "synced",
}));

vi.mock("@/db/index", () => ({
	db: {
		papers: {
			orderBy: vi.fn(() => ({
				reverse: vi.fn(() => ({
					toArray: vi.fn(() => Promise.resolve([])),
				})),
			})),
		},
	},
	isDbAvailable: () => true,
}));

vi.mock("@/lib/logger", () => ({
	createLogger: () => ({ error: vi.fn(), info: vi.fn(), warn: vi.fn() }),
}));

const mockSyncTrajectory = vi.hoisted(() => vi.fn());
vi.mock("@/lib/recommendation", () => ({
	syncTrajectory: mockSyncTrajectory,
}));

vi.mock("@/hooks/useLayoutState", () => ({
	useLayoutState: () => ({
		sidebarWidth: 300,
		setSidebarWidth: vi.fn(),
		isResizing: false,
		setIsResizing: vi.fn(),
		isLeftSidebarOpen: true,
		setIsLeftSidebarOpen: vi.fn(),
		isRightSidebarOpen: false,
		setIsRightSidebarOpen: vi.fn(),
		isMobile: false,
	}),
	clampWidth: (w: number) => w,
}));

vi.mock("@/hooks/usePinchZoom", () => ({
	usePinchZoom: () => ({
		zoom: 1,
		resetZoom: vi.fn(),
		zoomIn: vi.fn(),
		zoomOut: vi.fn(),
		containerRef: { current: null },
		onWheel: vi.fn(),
	}),
}));

vi.mock("@/hooks/useScrollTracking", () => ({
	useScrollTracking: () => vi.fn(),
}));

vi.mock("@/hooks/useSearchState", () => ({
	useSearchState: () => ({
		isSearchOpen: false,
		searchTerm: "",
		setSearchTerm: vi.fn(),
		searchMatches: [],
		currentMatchIndex: 0,
		currentSearchMatch: null,
		handleNextMatch: vi.fn(),
		handlePrevMatch: vi.fn(),
		handleCloseSearch: vi.fn(),
		handleSearchMatchesUpdate: vi.fn(),
	}),
}));

vi.mock("@/hooks/useServiceHealth", () => ({
	useServiceHealth: () => ({
		isHealthy: true,
		isMaintenance: false,
		message: null,
		reportFailure: vi.fn(),
	}),
}));

// usePaperLifecycle はタイマー・sendBeacon を使うためモック化
vi.mock("@/hooks/usePaperLifecycle", () => ({
	usePaperLifecycle: vi.fn(),
}));

// usePaperLibrary はリトライタイマーを持つためモック化
let mockUploadedPapers: any[] = [];
const mockDeletePaper = vi.fn();
const mockRefreshPapers = vi.fn();

vi.mock("@/hooks/usePaperLibrary", () => ({
	usePaperLibrary: () => ({
		uploadedPapers: mockUploadedPapers,
		isPapersLoading: false,
		refreshPapers: mockRefreshPapers,
		deletePaper: mockDeletePaper,
		setUploadedPapers: vi.fn(),
		setIsPapersLoading: vi.fn(),
	}),
}));

// useWordInteraction は純粋な useState のみなので実装を使用（モック不要）

import { useAppState } from "./useAppState";

const mockPapers = [
	{ paper_id: "p1", title: "Paper 1", created_at: new Date().toISOString() },
	{ paper_id: "p2", title: "Paper 2", created_at: new Date().toISOString() },
];

describe("useAppState", () => {
	beforeEach(() => {
		vi.clearAllMocks();
		mockUser = { id: "test-user", name: "Test User" };
		mockIsGuest = false;
		mockUploadedPapers = [...mockPapers];
		mockDeletePaper.mockResolvedValue(false);
		mockRefreshPapers.mockResolvedValue(undefined);
		mockGetCachedPaper.mockResolvedValue(null);

		global.fetch = vi.fn((url: string) => {
			if ((url as string).endsWith("/api/config")) {
				return Promise.resolve({
					json: () => Promise.resolve({ app_env: "test" }),
					status: 200,
				});
			}
			return Promise.resolve({
				json: () => Promise.resolve({}),
				ok: true,
				status: 200,
			});
		}) as any;

		global.window.confirm = vi.fn(() => true);
	});

	describe("handlePaperSelect", () => {
		it("sets currentPaperId and opens right sidebar", () => {
			const { result } = renderHook(() => useAppState());

			expect(result.current.currentPaperId).toBeNull();

			act(() => {
				result.current.handlePaperSelect({ paper_id: "p1" });
			});

			expect(result.current.currentPaperId).toBe("p1");
		});
	});

	describe("handleDeletePaper", () => {
		it("calls window.confirm then deletePaper with correct args", async () => {
			const { result } = renderHook(() => useAppState());

			act(() => {
				result.current.handlePaperSelect({ paper_id: "p1" });
			});

			const mockEvent = { stopPropagation: vi.fn() } as any;
			await act(async () => {
				await result.current.handleDeletePaper(mockEvent, { paper_id: "p1" });
			});

			expect(mockEvent.stopPropagation).toHaveBeenCalled();
			expect(window.confirm).toHaveBeenCalled();
			expect(mockDeletePaper).toHaveBeenCalledWith(
				{ paper_id: "p1" },
				"p1",
				mockUser,
			);
		});

		it("clears currentPaperId when the current paper is deleted", async () => {
			mockDeletePaper.mockResolvedValue(true);
			const { result } = renderHook(() => useAppState());

			act(() => {
				result.current.handlePaperSelect({ paper_id: "p1" });
			});
			expect(result.current.currentPaperId).toBe("p1");

			const mockEvent = { stopPropagation: vi.fn() } as any;
			await act(async () => {
				await result.current.handleDeletePaper(mockEvent, { paper_id: "p1" });
			});

			expect(result.current.currentPaperId).toBeNull();
		});

		it("does nothing when user cancels the confirm dialog", async () => {
			global.window.confirm = vi.fn(() => false);
			const { result } = renderHook(() => useAppState());

			const mockEvent = { stopPropagation: vi.fn() } as any;
			await act(async () => {
				await result.current.handleDeletePaper(mockEvent, { paper_id: "p1" });
			});

			expect(mockDeletePaper).not.toHaveBeenCalled();
		});
	});

	describe("handleWordClick", () => {
		it("calls syncTrajectory and switches to notes/translation tab", () => {
			const { result } = renderHook(() => useAppState());

			act(() => {
				result.current.handlePaperSelect({ paper_id: "p1" });
			});

			act(() => {
				result.current.handleWordClick(
					"hello",
					"ctx",
					{ page: 1, x: 10, y: 10 },
					0.9,
				);
			});

			expect(mockSyncTrajectory).toHaveBeenCalledWith(
				expect.objectContaining({
					paper_id: "p1",
					word_clicks: [
						expect.objectContaining({ word: "hello", context: "ctx" }),
					],
				}),
				mockToken,
			);
			expect(result.current.activeTab).toBe("notes");
			expect(result.current.dictSubTab).toBe("translation");
			expect(result.current.translationWord).toBe("hello");
		});

		it("does not call syncTrajectory when no paper is selected", () => {
			const { result } = renderHook(() => useAppState());

			act(() => {
				result.current.handleWordClick("hello", "ctx");
			});

			expect(mockSyncTrajectory).not.toHaveBeenCalled();
		});
	});

	describe("handleAskAI", () => {
		it("switches to notes/figures tab when an image URL is provided", () => {
			const { result } = renderHook(() => useAppState());

			act(() => {
				result.current.handleAskAI("explain", "img.jpg", {
					page: 1,
					x: 0,
					y: 0,
				});
			});

			expect(result.current.activeTab).toBe("notes");
			expect(result.current.dictSubTab).toBe("figures");
		});

		it("switches to notes/explanation tab for text-only requests", () => {
			const { result } = renderHook(() => useAppState());

			act(() => {
				result.current.handleAskAI("explain this concept");
			});

			expect(result.current.activeTab).toBe("notes");
			expect(result.current.dictSubTab).toBe("explanation");
		});
	});

	describe("handleTextSelect", () => {
		it("switches to comments tab", () => {
			const { result } = renderHook(() => useAppState());

			act(() => {
				result.current.handleTextSelect("selected text", {
					page: 1,
					x: 0,
					y: 0,
				});
			});

			expect(result.current.activeTab).toBe("comments");
		});
	});

	describe("guest to login transition", () => {
		it("calls claim API when user transitions from guest (null) to logged-in", async () => {
			mockUser = null;
			mockIsGuest = true;
			mockGetCachedPaper.mockResolvedValue({
				id: "guest-p1",
				title: "Guest Paper",
				file_hash: "hash123",
				ocr_text: "text",
				layout_json: null,
			});

			const claimFetch = vi.fn(() =>
				Promise.resolve({
					ok: true,
					json: () => Promise.resolve({ claimed: true }),
				}),
			);
			(global.fetch as any).mockImplementation((url: string) => {
				if (url.endsWith("/api/papers/claim")) return claimFetch();
				if (url.endsWith("/api/config"))
					return Promise.resolve({
						json: () => Promise.resolve({ app_env: "test" }),
						status: 200,
					});
				return Promise.resolve({ json: () => Promise.resolve({}), ok: true });
			});

			const { result, rerender } = renderHook(() => useAppState());

			// ゲスト状態で論文を選択
			act(() => {
				result.current.handlePaperSelect({ paper_id: "guest-p1" });
			});
			expect(result.current.currentPaperId).toBe("guest-p1");

			// ログイン状態に遷移
			mockUser = { id: "new-user", name: "Logged User" };
			mockIsGuest = false;
			rerender();

			await waitFor(() => {
				expect(claimFetch).toHaveBeenCalled();
			});

			expect(mockGetCachedPaper).toHaveBeenCalledWith("guest-p1");
		});
	});
});

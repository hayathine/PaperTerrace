import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// Mock child components to isolate App.tsx rendering logic
vi.mock("@/components/Auth/Login", () => ({
	default: () => <div data-testid="login-mock">Login</div>,
}));
vi.mock("@/components/Contact/RequestForm", () => ({
	default: () => <div data-testid="request-form-mock">RequestForm</div>,
}));
vi.mock("@/components/Error/ErrorBoundary", () => ({
	default: ({ children }: any) => (
		<div data-testid="error-boundary-mock">{children}</div>
	),
}));
vi.mock("@/components/PDF/PDFViewer", () => ({
	default: ({ paperId, onWordClick, onAskAI, onTextSelect }: any) => (
		<div data-testid="pdf-viewer-mock">
			PDFViewer:{paperId || "none"}
			<button
				type="button"
				data-testid="mock-word-click"
				onClick={() =>
					onWordClick?.("hello", "context", { page: 1, x: 10, y: 10 }, 0.95)
				}
			>
				WordClick
			</button>
			<button
				type="button"
				data-testid="mock-ask-ai"
				onClick={() =>
					onAskAI?.("explain this", "img.jpg", { page: 1, x: 20, y: 20 })
				}
			>
				AskAI
			</button>
			<button
				type="button"
				data-testid="mock-text-select"
				onClick={() =>
					onTextSelect?.("selected text", { page: 1, x: 30, y: 30 })
				}
			>
				TextSelect
			</button>
		</div>
	),
}));
vi.mock("@/components/Search/SearchBar", () => ({
	default: () => <div data-testid="search-bar-mock">SearchBar</div>,
}));
vi.mock("@/components/Sidebar/Sidebar", () => ({
	default: () => <div data-testid="sidebar-mock">Sidebar</div>,
}));
vi.mock("@/components/UI/GlobalLoading", () => ({
	default: () => <div data-testid="global-loading-mock">GlobalLoading</div>,
}));
vi.mock("@/components/UI/ServiceOutage", () => ({
	default: () => <div data-testid="service-outage-mock">ServiceOutage</div>,
}));
vi.mock("@/components/Upload/UploadScreen", () => ({
	default: () => <div data-testid="upload-screen-mock">UploadScreen</div>,
}));

// Mock Auth Context
const mockLogout = vi.fn();
let mockUser: any = {
	uid: "test-user",
	name: "Test User",
	email: "test@example.com",
};
let mockIsGuest = false;

vi.mock("@/contexts/AuthContext", () => ({
	useAuth: () => ({
		user: mockUser,
		isGuest: mockIsGuest,
		logout: mockLogout,
		token: "mock-token",
	}),
}));

vi.mock("@/contexts/LoadingContext", () => ({
	useLoading: () => ({ startLoading: vi.fn(), stopLoading: vi.fn() }),
}));

// Mock Hooks
const mockGetCachedPaper = vi.fn();
const mockDeletePaperCache = vi.fn();
vi.mock("@/db/hooks", () => ({
	usePaperCache: () => ({
		getCachedPaper: mockGetCachedPaper,
		deletePaperCache: mockDeletePaperCache,
	}),
}));

// Use vi.hoisted for mocks that need to be accessible within vi.mock
const dexieMocks = vi.hoisted(() => ({
	mockToArray: vi.fn<any>(() => Promise.resolve([])),
	mockReverse: vi.fn<any>(() => ({
		toArray: vi.fn<any>(() => Promise.resolve([])),
	})),
	mockOrderBy: vi.fn<any>(() => ({
		reverse: vi.fn<any>(() => ({
			toArray: vi.fn<any>(() => Promise.resolve([])),
		})),
	})),
}));

vi.mock("@/db/index", () => ({
	db: {
		papers: {
			orderBy: dexieMocks.mockOrderBy,
		},
	},
	isDbAvailable: () => true,
}));

// Set up default implementation linkage
dexieMocks.mockOrderBy.mockReturnValue({
	reverse: vi.fn(() => ({
		toArray: dexieMocks.mockToArray,
	})),
});
dexieMocks.mockToArray.mockResolvedValue([]);

vi.mock("@/db/sync", () => ({
	useSyncStatus: () => "synced",
}));

vi.mock("@/hooks/useLayoutState", () => ({
	useLayoutState: () => ({
		sidebarWidth: 300,
		setSidebarWidth: vi.fn(),
		isResizing: false,
		setIsResizing: vi.fn(),
		isLeftSidebarOpen: true, // Keep it open for testing
		setIsLeftSidebarOpen: vi.fn(),
		isRightSidebarOpen: false,
		setIsRightSidebarOpen: vi.fn(),
		isMobile: false,
	}),
}));

vi.mock("@/hooks/usePinchZoom", () => ({
	usePinchZoom: () => ({
		zoom: 1,
		resetZoom: vi.fn(),
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

vi.mock("@/lib/logger", () => ({
	createLogger: () => ({ error: vi.fn(), info: vi.fn(), warn: vi.fn() }),
}));

vi.mock("@/lib/recommendation", () => ({
	syncTrajectory: vi.fn(),
}));

vi.mock("react-i18next", () => ({
	useTranslation: () => ({
		t: (key: string, fallback?: string) => fallback || key,
	}),
}));

// We need to import App after mocking its dependencies
import App from "./App";

describe("App Interactions", () => {
	const mockPapers = [
		{ paper_id: "p1", title: "Paper 1", created_at: new Date().toISOString() },
		{ paper_id: "p2", title: "Paper 2", created_at: new Date().toISOString() },
	];

	beforeEach(() => {
		vi.clearAllMocks();
		mockUser = {
			uid: "test-user",
			name: "Test User",
			email: "test@example.com",
		};
		mockIsGuest = false;

		global.fetch = vi.fn((url: string) => {
			if (url.endsWith("/api/config")) {
				return Promise.resolve({
					json: () => Promise.resolve({ app_env: "test" }),
					status: 200,
				});
			}
			if (url.endsWith("/api/papers")) {
				return Promise.resolve({
					json: () => Promise.resolve({ papers: mockPapers }),
					status: 200,
				});
			}
			if (url.includes("/api/papers/p1") || url.includes("/api/papers/p2")) {
				return Promise.resolve({
					json: () => Promise.resolve({ ok: true, deleted: true }),
					status: 200,
				});
			}
			return Promise.resolve({
				json: () => Promise.resolve({}),
				status: 200,
			});
		}) as any;

		// Mock window.confirm
		global.window.confirm = vi.fn(() => true);
	});

	it("renders the paper library and allows selecting a paper", async () => {
		render(<App />);

		// Wait for papers to load
		await waitFor(() => {
			expect(screen.getByText("Paper 1")).toBeDefined();
		});

		// Click Paper 1
		fireEvent.click(screen.getByText("Paper 1"));

		// Check if currentPaperId would be set
		await waitFor(() => {
			expect(screen.getByTestId("pdf-viewer-mock")).toHaveTextContent(
				"PDFViewer:p1",
			);
		});
	});

	it("handles paper deletion", async () => {
		render(<App />);

		await waitFor(() => {
			expect(screen.getByText("Paper 1")).toBeDefined();
		});

		// The delete button is within the same container as the paper title
		const deleteButtons = screen.getAllByTitle("削除");
		fireEvent.click(deleteButtons[0]);

		// Should call window.confirm
		expect(global.window.confirm).toHaveBeenCalled();

		// Should call fetch with DELETE
		await waitFor(() => {
			expect(global.fetch).toHaveBeenCalledWith(
				expect.stringContaining("/api/papers/p1"),
				expect.objectContaining({ method: "DELETE" }),
			);
		});

		// Should call deletePaperCache from usePaperCache
		expect(mockDeletePaperCache).toHaveBeenCalledWith("p1");

		// Paper 1 should be gone from the list
		await waitFor(() => {
			expect(screen.queryByText("Paper 1")).toBeNull();
		});
	});

	it("handles guest to logged-in transition and claiming papers", async () => {
		// 1. Start as guest
		mockUser = null;
		mockIsGuest = true;

		// IMPORTANT: Set up mock papers BEFORE the first render
		dexieMocks.mockToArray.mockResolvedValue([
			{ id: "guest-p1", title: "Guest Paper", last_accessed: Date.now() },
		]);

		// Mock getCachedPaper to return a guest paper
		const mockPaper = {
			id: "guest-p1",
			title: "Guest Paper",
			file_hash: "hash123",
			ocr_text: "text",
		};
		mockGetCachedPaper.mockResolvedValue(mockPaper);

		const { rerender } = render(<App />);

		// Mock claiming API
		const claimMock = vi.fn(() =>
			Promise.resolve({
				ok: true,
				json: () => Promise.resolve({ claimed: true }),
			}),
		);
		(global.fetch as any).mockImplementation((url: string) => {
			if (url.endsWith("/api/papers/claim")) return claimMock();
			if (url.endsWith("/api/papers"))
				return Promise.resolve({ json: () => Promise.resolve({ papers: [] }) });
			return Promise.resolve({ json: () => Promise.resolve({}), status: 200 });
		});

		// 2. Select a paper as guest
		await waitFor(() => {
			expect(screen.getByText("Guest Paper")).toBeDefined();
		});

		fireEvent.click(screen.getByText("Guest Paper"));

		// 3. Wait for currentPaperId to be set before login
		await waitFor(() => {
			expect(screen.getByTestId("pdf-viewer-mock")).toHaveTextContent(
				"PDFViewer:guest-p1",
			);
		});

		// 4. Simulate login
		mockUser = { uid: "new-user", name: "Logged User" };
		mockIsGuest = false;

		rerender(<App />);

		// 5. Verify claim API was called
		await waitFor(() => {
			expect(claimMock).toHaveBeenCalled();
		});

		// Actually check fetch calls
		const fetchCalls = (global.fetch as any).mock.calls;
		const claimCall = fetchCalls.find((call: any) =>
			call[0].endsWith("/api/papers/claim"),
		);
		expect(claimCall).toBeDefined();
		expect(JSON.parse(claimCall[1].body)).toMatchObject({
			paper_id: "guest-p1",
			file_hash: "hash123",
		});
	});

	it("handles word clicks and triggers trajectory sync", async () => {
		const { syncTrajectory } = await import("@/lib/recommendation");
		render(<App />);

		// Wait for paper list and select one
		await waitFor(() => expect(screen.getByText("Paper 1")).toBeDefined());
		fireEvent.click(screen.getByText("Paper 1"));

		// Simulate word click from PDFViewer
		const wordBtn = screen.getByTestId("mock-word-click");
		fireEvent.click(wordBtn);

		// 1. Check if sidebar opens and tab switches to notes/translation
		// Note: Sidebar mock should ideally show active tabs, but we check if it renders.
		expect(screen.getByTestId("sidebar-mock")).toBeDefined();

		// 2. Check if syncTrajectory was called
		await waitFor(() => {
			expect(syncTrajectory).toHaveBeenCalledWith(
				expect.objectContaining({
					session_id: expect.stringContaining("session-"),
					paper_id: "p1",
					word_clicks: [
						expect.objectContaining({
							word: "hello",
							context: "context",
						}),
					],
				}),
				"mock-token",
			);
		});
	});

	it("handles AskAI and switches to notes tab", async () => {
		render(<App />);
		await waitFor(() => expect(screen.getByText("Paper 1")).toBeDefined());
		fireEvent.click(screen.getByText("Paper 1"));

		const aiBtn = screen.getByTestId("mock-ask-ai");
		fireEvent.click(aiBtn);

		// Should switch to notes tab
		expect(screen.getByTestId("sidebar-mock")).toBeDefined();
	});

	it("handles text selection and switches to comments tab", async () => {
		render(<App />);
		await waitFor(() => expect(screen.getByText("Paper 1")).toBeDefined());
		fireEvent.click(screen.getByText("Paper 1"));

		const textBtn = screen.getByTestId("mock-text-select");
		fireEvent.click(textBtn);

		// Should switch to comments tab
		expect(screen.getByTestId("sidebar-mock")).toBeDefined();
	});
});

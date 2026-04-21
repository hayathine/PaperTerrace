import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// Child components
vi.mock("@/components/Auth/Login", () => ({
	default: () => <div data-testid="login-mock">Login</div>,
}));
vi.mock("@/components/Contact/RequestForm", () => ({
	default: () => <div data-testid="request-form-mock" />,
}));
vi.mock("@/components/Error/ErrorBoundary", () => ({
	default: ({ children }: any) => <div>{children}</div>,
}));
vi.mock("@/components/Help/HelpAssistant", () => ({
	default: () => <div data-testid="help-assistant-mock" />,
}));
vi.mock("@/components/PDF/PDFViewer", () => ({
	default: ({ paperId, onWordClick, onAskAI, onTextSelect }: any) => (
		<div data-testid="pdf-viewer-mock">
			PDFViewer:{paperId || "none"}
			<button
				type="button"
				data-testid="mock-word-click"
				onClick={() =>
					onWordClick?.("hello", "ctx", { page: 1, x: 10, y: 10 }, 0.95)
				}
			>
				WordClick
			</button>
			<button
				type="button"
				data-testid="mock-ask-ai"
				onClick={() =>
					onAskAI?.("explain", "img.jpg", { page: 1, x: 20, y: 20 })
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
	default: () => <div data-testid="search-bar-mock" />,
}));
vi.mock("@/components/Sidebar/Sidebar", () => ({
	default: () => <div data-testid="sidebar-mock" />,
}));
vi.mock("@/components/UI/GlobalLoading", () => ({ default: () => null }));
vi.mock("@/components/UI/ServiceOutage", () => ({ default: () => null }));
vi.mock("@/components/Upload/UploadScreen", () => ({
	default: () => <div data-testid="upload-screen-mock" />,
}));

// react-router-dom: /* ルートのみレンダリングして Dashboard の lazy import を回避
vi.mock("react-router-dom", () => ({
	Routes: ({ children }: any) => <>{children}</>,
	Route: ({ path, element }: any) => (path === "/*" ? element : null),
	useNavigate: () => vi.fn(),
	useLocation: () => ({ pathname: "/", search: "", hash: "", state: null }),
}));

// ---- useAppState モック ----
const mockHandlePaperSelect = vi.fn();
const mockHandleDeletePaper = vi.fn();
const mockHandleWordClick = vi.fn();
const mockHandleAskAI = vi.fn();
const mockHandleTextSelect = vi.fn();

let mockAppState: any;

vi.mock("@/hooks/useAppState", () => ({
	useAppState: () => mockAppState,
}));

const mockPapers = [
	{ paper_id: "p1", title: "Paper 1", created_at: new Date().toISOString() },
	{ paper_id: "p2", title: "Paper 2", created_at: new Date().toISOString() },
];

function buildState(overrides: Record<string, unknown> = {}) {
	return {
		// Auth
		user: { id: "test-user", name: "Test User", email: "test@example.com" },
		isGuest: false,
		logout: vi.fn(),
		token: "mock-token",
		navigate: vi.fn(),
		t: (key: string) => key,
		// Health
		isHealthy: true,
		isMaintenance: false,
		healthMessage: null,
		// File/Paper
		uploadFile: null,
		currentPaperId: null,
		isAnalyzing: false,
		uploadedPapers: [],
		isPapersLoading: false,
		// Session/Tabs
		sessionId: "session-test",
		activeTab: "chat",
		setActiveTab: vi.fn(),
		dictSubTab: "translation",
		setDictSubTab: vi.fn(),
		showLoginModal: false,
		setShowLoginModal: vi.fn(),
		// Layout
		sidebarWidth: 300,
		setSidebarWidth: vi.fn(),
		isResizing: false,
		setIsResizing: vi.fn(),
		isLeftSidebarOpen: true,
		setIsLeftSidebarOpen: vi.fn(),
		isRightSidebarOpen: false,
		setIsRightSidebarOpen: vi.fn(),
		isMobile: false,
		// Word state
		translationWord: undefined,
		translationContext: undefined,
		translationCoordinates: undefined,
		translationConf: undefined,
		explanationWord: undefined,
		explanationContext: undefined,
		explanationCoordinates: undefined,
		selectedWord: undefined,
		selectedContext: undefined,
		selectedCoordinates: undefined,
		selectedImage: undefined,
		jumpTarget: null,
		pendingFigureId: null,
		setPendingFigureId: vi.fn(),
		pendingChatPrompt: null,
		setPendingChatPrompt: vi.fn(),
		selectedFigure: null,
		activeEvidence: undefined,
		setActiveEvidence: vi.fn(),
		// Zoom
		zoom: 1,
		resetZoom: vi.fn(),
		zoomIn: vi.fn(),
		zoomOut: vi.fn(),
		zoomContainerRef: { current: null },
		handleZoomWheel: vi.fn(),
		// Scroll / Config / Mode / Search
		handleScroll: vi.fn(),
		appEnv: "test",
		maxPdfSize: 50,
		pdfMode: "plaintext",
		setPdfMode: vi.fn(),
		isModeTransitionPending: false,
		startModeTransition: (fn: () => void) => fn(),
		syncStatus: "synced",
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
		// Handlers
		handlePaperLoaded: vi.fn(),
		handlePaperSelect: mockHandlePaperSelect,
		handleDeletePaper: mockHandleDeletePaper,
		handleDirectFileSelect: vi.fn(),
		handleFileChange: vi.fn(),
		handleWordClick: mockHandleWordClick,
		handleTextSelect: mockHandleTextSelect,
		handleAreaSelect: vi.fn(),
		handleJumpToLocation: vi.fn(),
		handleAnalysisStatusChange: vi.fn(),
		handleAskAI: mockHandleAskAI,
		handleFigureSelect: vi.fn(),
		handleResizeKeyDown: vi.fn(),
		...overrides,
	};
}

import App from "./App";

describe("App - JSX wiring", () => {
	beforeEach(() => {
		vi.clearAllMocks();
		mockAppState = buildState();
	});

	it("renders papers from uploadedPapers in the sidebar", () => {
		mockAppState = buildState({ uploadedPapers: mockPapers });
		render(<App />);

		expect(screen.getByText("Paper 1")).toBeDefined();
		expect(screen.getByText("Paper 2")).toBeDefined();
	});

	it("calls handlePaperSelect with the correct paper when clicked", () => {
		mockAppState = buildState({ uploadedPapers: mockPapers });
		render(<App />);

		fireEvent.click(screen.getByText("Paper 1"));

		expect(mockHandlePaperSelect).toHaveBeenCalledWith(
			expect.objectContaining({ paper_id: "p1" }),
		);
	});

	it("shows delete buttons when appEnv is not prod and calls handleDeletePaper", () => {
		mockAppState = buildState({ uploadedPapers: mockPapers, appEnv: "test" });
		render(<App />);

		const deleteButtons = screen.getAllByTitle("削除");
		expect(deleteButtons).toHaveLength(2);

		fireEvent.click(deleteButtons[0]);

		expect(mockHandleDeletePaper).toHaveBeenCalledWith(
			expect.any(Object),
			expect.objectContaining({ paper_id: "p1" }),
		);
	});

	it("hides delete buttons when appEnv is prod", () => {
		mockAppState = buildState({ uploadedPapers: mockPapers, appEnv: "prod" });
		render(<App />);

		expect(screen.queryAllByTitle("削除")).toHaveLength(0);
	});

	it("passes currentPaperId to PDFViewer", () => {
		mockAppState = buildState({ currentPaperId: "p1" });
		render(<App />);

		expect(screen.getByTestId("pdf-viewer-mock")).toHaveTextContent(
			"PDFViewer:p1",
		);
	});

	it("wires onWordClick to handleWordClick", () => {
		mockAppState = buildState({ currentPaperId: "p1" });
		render(<App />);

		fireEvent.click(screen.getByTestId("mock-word-click"));

		expect(mockHandleWordClick).toHaveBeenCalledWith(
			"hello",
			"ctx",
			{ page: 1, x: 10, y: 10 },
			0.95,
		);
	});

	it("wires onAskAI to handleAskAI", () => {
		mockAppState = buildState({ currentPaperId: "p1" });
		render(<App />);

		fireEvent.click(screen.getByTestId("mock-ask-ai"));

		expect(mockHandleAskAI).toHaveBeenCalledWith("explain", "img.jpg", {
			page: 1,
			x: 20,
			y: 20,
		});
	});

	it("wires onTextSelect to handleTextSelect", () => {
		mockAppState = buildState({ currentPaperId: "p1" });
		render(<App />);

		fireEvent.click(screen.getByTestId("mock-text-select"));

		expect(mockHandleTextSelect).toHaveBeenCalledWith("selected text", {
			page: 1,
			x: 30,
			y: 30,
		});
	});
});

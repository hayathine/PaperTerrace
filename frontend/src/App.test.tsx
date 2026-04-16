import { render, screen } from "@testing-library/react";
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
	default: () => <div data-testid="pdf-viewer-mock">PDFViewer</div>,
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

// Mock Contexts
vi.mock("@/contexts/AuthContext", () => ({
	useAuth: () => ({
		user: null,
		isGuest: false,
		logout: vi.fn(),
		token: "mock-token",
	}),
}));
vi.mock("@/contexts/LoadingContext", () => ({
	useLoading: () => ({ startLoading: vi.fn(), stopLoading: vi.fn() }),
}));

// Mock Hooks
vi.mock("@/db/hooks", () => ({
	usePaperCache: () => ({ getCachedPaper: vi.fn() }),
	useBookmarks: () => ({
		addBookmark: vi.fn(),
		getBookmarks: vi.fn(() => Promise.resolve([])),
		getPageBookmarks: vi.fn(() => Promise.resolve(false)),
		deleteBookmark: vi.fn(),
	}),
}));
vi.mock("@/db/sync", () => ({
	useSyncStatus: () => "synced",
}));
vi.mock("@/hooks/useLayoutState", () => ({
	useLayoutState: () => ({
		sidebarWidth: 300,
		setSidebarWidth: vi.fn(),
		isResizing: false,
		setIsResizing: vi.fn(),
		isLeftSidebarOpen: false,
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

// Mock Lib functions
vi.mock("@/lib/logger", () => ({
	createLogger: () => ({ error: vi.fn(), info: vi.fn(), warn: vi.fn() }),
}));
vi.mock("@/lib/recommendation", () => ({
	syncTrajectory: vi.fn(),
}));
vi.mock("react-router-dom", () => ({
	Routes: ({ children }: any) => <>{children}</>,
	Route: ({ element }: any) => <>{element}</>,
	useNavigate: () => vi.fn(),
	useLocation: () => ({
		pathname: "/",
		search: "",
		hash: "",
		state: null,
	}),
}));

// Mock Translations
vi.mock("react-i18next", () => ({
	useTranslation: () => ({
		t: (key: string, fallback?: string) => fallback || key,
	}),
}));

// We need to import App after mocking its dependencies
import App from "./App";

describe("App Component", () => {
	beforeEach(() => {
		vi.clearAllMocks();
		global.fetch = vi.fn(() =>
			Promise.resolve({
				json: () => Promise.resolve({ app_env: "test" }),
				status: 200,
			}),
		) as any;
	});

	it("should render error boundary and main layout successfully", () => {
		render(<App />);
		// Validate that ErrorBoundary wraps the app
		expect(screen.getByTestId("error-boundary-mock")).toBeDefined();
		// Header should contain the "PaperTerrace" text in the left sidebar
		expect(screen.getByText("PaperTerrace")).toBeDefined();
		// It renders the sidebar
		expect(screen.getByTestId("sidebar-mock")).toBeDefined();
	});
});

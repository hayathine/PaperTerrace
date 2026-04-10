import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// Mock child components
vi.mock("@/components/Auth/Login", () => ({ default: () => <div>Login</div> }));
vi.mock("@/components/Contact/RequestForm", () => ({
	default: () => <div>RequestForm</div>,
}));
vi.mock("@/components/Error/ErrorBoundary", () => ({
	default: ({ children }: any) => <div>{children}</div>,
}));
vi.mock("@/components/PDF/PDFViewer", () => ({
	default: () => <div>PDFViewer</div>,
}));
vi.mock("@/components/Search/SearchBar", () => ({
	default: () => <div>SearchBar</div>,
}));
vi.mock("@/components/Sidebar/Sidebar", () => ({
	default: () => <div>Sidebar</div>,
}));
vi.mock("@/components/UI/GlobalLoading", () => ({
	default: () => <div>GlobalLoading</div>,
}));
vi.mock("@/components/UI/ServiceOutage", () => ({
	default: ({ isMaintenance, message }: any) => (
		<div data-testid="service-outage">
			{isMaintenance ? "maintenance" : "outage"}: {message}
		</div>
	),
}));
vi.mock("@/components/Upload/UploadScreen", () => ({
	default: () => <div>UploadScreen</div>,
}));

// Mock Hooks & Contexts
vi.mock("@/contexts/AuthContext", () => ({
	useAuth: () => ({ user: null, isGuest: true, logout: vi.fn(), token: null }),
}));
vi.mock("@/contexts/LoadingContext", () => ({
	useLoading: () => ({ startLoading: vi.fn(), stopLoading: vi.fn() }),
}));
vi.mock("@/db/hooks", () => ({
	usePaperCache: () => ({ getCachedPaper: vi.fn() }),
}));
vi.mock("@/db/sync", () => ({ useSyncStatus: () => "synced" }));
vi.mock("@/hooks/useLayoutState", () => ({
	useLayoutState: () => ({
		sidebarWidth: 300,
		setSidebarWidth: vi.fn(),
		isResizing: false,
		setIsResizing: vi.fn(),
		isLeftSidebarOpen: false,
		isRightSidebarOpen: false,
		setIsLeftSidebarOpen: vi.fn(),
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
		searchMatches: [],
		currentMatchIndex: 0,
		handleNextMatch: vi.fn(),
		handlePrevMatch: vi.fn(),
		handleCloseSearch: vi.fn(),
	}),
}));

// The actual mock for health that we will change in tests
const mockUseServiceHealth = vi.fn();

vi.mock("@/hooks/useServiceHealth", () => ({
	useServiceHealth: () => mockUseServiceHealth(),
}));

vi.mock("react-i18next", () => ({
	useTranslation: () => ({ t: (k: string) => k }),
}));
vi.mock("react-router-dom", () => ({
	Routes: ({ children }: any) => <>{children}</>,
	Route: ({ element }: any) => <>{element}</>,
	useNavigate: () => vi.fn(),
}));

import App from "./App";

describe("App Service Outage Handling", () => {
	beforeEach(() => {
		vi.clearAllMocks();
		global.fetch = vi.fn().mockResolvedValue({
			ok: true,
			json: () => Promise.resolve({ app_env: "test" }),
		});
		// Default to healthy
		mockUseServiceHealth.mockReturnValue({
			isHealthy: true,
			isMaintenance: false,
			message: null,
			reportFailure: vi.fn(),
		});
	});

	it("should show ServiceOutage when isHealthy is false", async () => {
		mockUseServiceHealth.mockReturnValue({
			isHealthy: false,
			isMaintenance: false,
			message: "Backend Down",
			reportFailure: vi.fn(),
		});

		render(<App />);

		await waitFor(() => {
			const outage = screen.queryByTestId("service-outage");
			expect(outage).not.toBeNull();
			expect(outage?.textContent).toContain("outage: Backend Down");
		});
	});

	it("should show ServiceOutage with maintenance type when isMaintenance is true", async () => {
		mockUseServiceHealth.mockReturnValue({
			isHealthy: false, // isHealthy must be false for App.tsx to show ServiceOutage
			isMaintenance: true,
			message: "Scheduled Maintenance",
			reportFailure: vi.fn(),
		});

		render(<App />);

		await waitFor(() => {
			const outage = screen.queryByTestId("service-outage");
			expect(outage).not.toBeNull();
			expect(outage?.textContent).toContain(
				"maintenance: Scheduled Maintenance",
			);
		});
	});
});

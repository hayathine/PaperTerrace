/**
 * @vitest-environment jsdom
 */
import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

// Mock child components/libraries at the very top
vi.mock("@/contexts/AuthContext", () => ({
	useAuth: () => ({
		user: {
			name: "Test User",
			email: "test@example.com",
			image: "https://example.com/avatar.jpg",
			createdAt: "2023-01-01T00:00:00Z",
		},
		token: "mock-token",
		isGuest: false,
	}),
}));

const {
	mockFetchUserStats,
	mockFetchUserPapers,
	mockFetchUserTranslations,
	mockGetBookmarks,
} = vi.hoisted(() => ({
	mockFetchUserStats: vi.fn().mockResolvedValue({
		paper_count: 5,
		note_count: 10,
		translation_count: 15,
		chat_count: 20,
	}),
	mockFetchUserPapers: vi.fn().mockResolvedValue({
		papers: [
			{
				paper_id: "paper1",
				title: "Unique Paper List Title",
				created_at: "2023-05-01T00:00:00Z",
				tags: ["tag1"],
			},
		],
	}),
	mockFetchUserTranslations: vi.fn().mockResolvedValue({
		translations: [
			{
				term: "hello",
				note: "greeting",
				page_number: 1,
				created_at: "2023-05-02T00:00:00Z",
			},
		],
		total: 1,
		page: 1,
		per_page: 20,
	}),
	mockGetBookmarks: vi.fn().mockResolvedValue([
		{
			id: "bm1",
			paper_id: "paper1",
			paper_title: "Unique Bookmark Title",
			page_number: 5,
			created_at: "2023-05-03T00:00:00Z",
		},
	]),
}));

vi.mock("@/lib/dashboard", async (importOriginal) => {
	const actual = (await importOriginal()) as any;
	return {
		...actual,
		fetchUserStats: mockFetchUserStats,
		fetchUserPapers: mockFetchUserPapers,
		fetchUserTranslations: mockFetchUserTranslations,
	};
});

vi.mock("@/db/hooks", () => ({
	useBookmarks: () => ({
		getBookmarks: mockGetBookmarks,
		deleteBookmark: vi.fn().mockResolvedValue(true),
	}),
}));

vi.mock("@/lib/logger", () => ({
	createLogger: () => ({ error: vi.fn(), info: vi.fn(), warn: vi.fn() }),
}));

import Dashboard from "./Dashboard";

describe("Dashboard Page", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("renders profile information correctly", async () => {
		render(
			<BrowserRouter>
				<Dashboard />
			</BrowserRouter>,
		);

		expect(screen.getByText("Test User")).toBeDefined();
		expect(screen.getByText("test@example.com")).toBeDefined();
	});

	it("renders stats sections correctly after loading", async () => {
		render(
			<BrowserRouter>
				<Dashboard />
			</BrowserRouter>,
		);

		expect(await screen.findByText("5")).toBeDefined();
		expect(await screen.findByText("10")).toBeDefined();
	});

	it("renders papers list correctly", async () => {
		render(
			<BrowserRouter>
				<Dashboard />
			</BrowserRouter>,
		);
		expect(
			await screen.findByText("Unique Paper List Title", {}, { timeout: 3000 }),
		).toBeDefined();
		expect(await screen.findByText("tag1")).toBeDefined();
	});

	it("renders bookmarks correctly", async () => {
		render(
			<BrowserRouter>
				<Dashboard />
			</BrowserRouter>,
		);

		expect(await screen.findByText(/P\.5/)).toBeDefined();
	});

	it("renders translation history correctly", async () => {
		render(
			<BrowserRouter>
				<Dashboard />
			</BrowserRouter>,
		);

		expect(await screen.findByText("hello")).toBeDefined();
	});

	it("filters papers based on search input", async () => {
		mockFetchUserPapers.mockResolvedValueOnce({
			papers: [
				{ paper_id: "p1", title: "React Guide", created_at: "2023-01-01" },
				{ paper_id: "p2", title: "Vue Guide", created_at: "2023-01-02" },
			],
		});

		render(
			<BrowserRouter>
				<Dashboard />
			</BrowserRouter>,
		);

		// Initially both should be there (though our mock only returned one in the default mock,
		// but here we override it)
		expect(await screen.findByText("React Guide")).toBeDefined();
		expect(await screen.findByText("Vue Guide")).toBeDefined();

		const searchInput = screen.getByPlaceholderText(/検索/);
		const { fireEvent } = await import("@testing-library/react");
		fireEvent.change(searchInput, { target: { value: "React" } });

		expect(screen.queryByText("React Guide")).not.toBeNull();
		expect(screen.queryByText("Vue Guide")).toBeNull();
	});

	it("handles translation pagination", async () => {
		mockFetchUserTranslations.mockResolvedValueOnce({
			translations: [{ term: "page1", created_at: "2023-01-01" }],
			total: 40, // 2 pages (20 per page)
			page: 1,
			per_page: 20,
		});

		render(
			<BrowserRouter>
				<Dashboard />
			</BrowserRouter>,
		);

		expect(await screen.findByText("page1")).toBeDefined();
		expect(screen.getByText("1 / 2")).toBeDefined();

		const nextButton = screen.getByText("次へ →");
		const { fireEvent } = await import("@testing-library/react");

		// When "Next" is clicked, it should call fetchUserTranslations for page 2
		mockFetchUserTranslations.mockResolvedValueOnce({
			translations: [{ term: "page2", created_at: "2023-01-01" }],
			total: 40,
			page: 2,
			per_page: 20,
		});

		fireEvent.click(nextButton);

		expect(await screen.findByText("page2")).toBeDefined();
		expect(screen.getByText("2 / 2")).toBeDefined();
	});

	it("shows empty state when no papers are found", async () => {
		mockFetchUserPapers.mockResolvedValueOnce({ papers: [] });

		render(
			<BrowserRouter>
				<Dashboard />
			</BrowserRouter>,
		);

		expect(await screen.findByText("論文はまだありません")).toBeDefined();
	});
});

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
				title: "Test Paper 1",
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
			paper_title: "Test Paper 1",
			page_number: 5,
			created_at: "2023-05-03T00:00:00Z",
		},
	]),
}));

vi.mock("@/lib/dashboard", () => ({
	fetchUserStats: mockFetchUserStats,
	fetchUserPapers: mockFetchUserPapers,
	fetchUserTranslations: mockFetchUserTranslations,
}));

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

		expect(await screen.findByText("Test Paper 1")).toBeDefined();
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
});

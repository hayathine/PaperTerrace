import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import Login from "./Login";

// Mock the hooks
vi.mock("react-i18next", () => ({
	useTranslation: () => ({
		t: (key: string) => key,
	}),
}));

vi.mock("../../contexts/AuthContext", () => ({
	useAuth: () => ({
		signInWithGoogle: vi.fn(),
		signInWithGithub: vi.fn(),
		signInWithGoogleRedirect: vi.fn(),
		signInWithGithubRedirect: vi.fn(),
	}),
}));

describe("Login Component", () => {
	it("renders PaperTerrace title", () => {
		render(<Login onGuestAccess={() => {}} />);
		expect(screen.getByText(/Paper/)).toBeDefined();
		expect(screen.getByText(/Terrace/)).toBeDefined();
	});

	it("renders login buttons", () => {
		render(<Login onGuestAccess={() => {}} />);
		expect(screen.getByText("auth.google")).toBeDefined();
		expect(screen.getByText("auth.github")).toBeDefined();
		expect(screen.getByText("auth.guest")).toBeDefined();
	});
});

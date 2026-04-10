import { render, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { authClient, getNeonJWT } from "@/lib/auth";
import { AuthProvider, useAuth } from "./AuthContext";

vi.unmock("@/contexts/AuthContext");

// Mock the authClient
vi.mock("@/lib/auth", () => ({
	authClient: {
		useSession: vi.fn(),
		signOut: vi.fn(),
		signIn: {
			social: vi.fn(),
		},
	},
	getNeonJWT: vi.fn(),
}));

// Test component to consume the context
const TestComponent = () => {
	const { user, loading, token, isGuest } = useAuth();
	if (loading) return <div data-testid="loading">Loading...</div>;
	return (
		<div>
			<div data-testid="user">{user ? user.email : "no-user"}</div>
			<div data-testid="token">{token || "no-token"}</div>
			<div data-testid="guest">{isGuest ? "guest" : "not-guest"}</div>
		</div>
	);
};

describe("AuthContext", () => {
	it("does not render children while loading", () => {
		(authClient.useSession as any).mockReturnValue({
			data: null,
			isPending: true,
		});

		const { queryByTestId } = render(
			<AuthProvider>
				<TestComponent />
			</AuthProvider>,
		);

		expect(queryByTestId("loading")).toBeNull();
	});

	it("provides guest state when no session exists", async () => {
		(authClient.useSession as any).mockReturnValue({
			data: null,
			isPending: false,
		});
		(getNeonJWT as any).mockResolvedValue(null);

		const { getByTestId } = render(
			<AuthProvider>
				<TestComponent />
			</AuthProvider>,
		);

		await waitFor(() => {
			expect(getByTestId("user").textContent).toBe("no-user");
			expect(getByTestId("token").textContent).toBe("no-token");
			expect(getByTestId("guest").textContent).toBe("guest");
		});
	});

	it("provides user and token when session exists", async () => {
		const mockSession = {
			user: { email: "test@example.com", name: "Test User" },
			session: { token: "mock-token-123" },
		};

		(authClient.useSession as any).mockReturnValue({
			data: mockSession,
			isPending: false,
		});
		(getNeonJWT as any).mockResolvedValue("mock-token-123");

		const { getByTestId } = render(
			<AuthProvider>
				<TestComponent />
			</AuthProvider>,
		);

		await waitFor(() => {
			expect(getByTestId("user").textContent).toBe("test@example.com");
			expect(getByTestId("token").textContent).toBe("mock-token-123");
			expect(getByTestId("guest").textContent).toBe("not-guest");
		});
	});

	it("clears state on logout", async () => {
		const mockSession = {
			user: { email: "test@example.com" },
			session: { token: "token" },
		};

		(authClient.useSession as any).mockReturnValue({
			data: mockSession,
			isPending: false,
		});

		let authFunctions: any;
		const LogoutButton = () => {
			authFunctions = useAuth();
			return (
				<button type="button" onClick={authFunctions.logout}>
					Logout
				</button>
			);
		};

		(getNeonJWT as any).mockResolvedValue("token");

		const { findByText, getByTestId } = render(
			<AuthProvider>
				<TestComponent />
				<LogoutButton />
			</AuthProvider>,
		);

		// Trigger logout
		const button = await findByText("Logout");
		button.click();

		await waitFor(() => {
			expect(authClient.signOut).toHaveBeenCalled();
			expect(getByTestId("user").textContent).toBe("no-user");
			expect(getByTestId("token").textContent).toBe("no-token");
			expect(getByTestId("guest").textContent).toBe("guest");
		});
	});
});

import { describe, expect, it, vi } from "vitest";
import { authClient, getNeonJWT } from "./auth";

// Mock the external module
vi.mock("@neondatabase/auth", () => ({
	createAuthClient: vi.fn(() => ({
		useSession: vi.fn(),
		signIn: { social: vi.fn() },
		signOut: vi.fn(),
	})),
	createInternalNeonAuth: vi.fn(() => ({
		getJWTToken: vi.fn().mockResolvedValue("mock-jwt-token"),
	})),
}));

vi.mock("@neondatabase/auth/react", () => ({
	BetterAuthReactAdapter: vi.fn(),
}));

describe("auth lib", () => {
	it("returns JWT from neon auth internal", async () => {
		const token = await getNeonJWT();
		expect(token).toBe("mock-jwt-token");
	});

	it("exports authClient", () => {
		expect(authClient).toBeDefined();
	});
});

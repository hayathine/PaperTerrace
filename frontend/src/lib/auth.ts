import { createAuthClient } from "@neondatabase/auth";
import { BetterAuthReactAdapter } from "@neondatabase/auth/react";

// VITE_NEON_AUTH_URL should be set in .env (e.g. https://<project>.neon.tech/auth)
export const authClient = createAuthClient(import.meta.env.VITE_NEON_AUTH_URL, {
	adapter: BetterAuthReactAdapter(),
});

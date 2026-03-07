import { createAuthClient } from "@neondatabase/neon-js/auth";

// VITE_NEON_AUTH_URL should be set in .env (e.g. https://<project>.neon.tech/auth)
export const authClient = createAuthClient(import.meta.env.VITE_NEON_AUTH_URL);

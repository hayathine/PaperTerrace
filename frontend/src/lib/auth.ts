import { createAuthClient, createInternalNeonAuth } from "@neondatabase/auth";
import { BetterAuthReactAdapter } from "@neondatabase/auth/react";

// Better Auth React client (for useSession, signIn.social, signOut, etc.)
export const authClient = createAuthClient(import.meta.env.VITE_NEON_AUTH_URL, {
	adapter: BetterAuthReactAdapter(),
});

// JWT 取得用の内部インスタンス（session.session.token は opaque token のため別途取得が必要）
const _neonAuthInternal = createInternalNeonAuth(
	import.meta.env.VITE_NEON_AUTH_URL,
	{ adapter: BetterAuthReactAdapter() },
);

// Neon Auth JWT を返す（CF Workers / バックエンドの Bearer 認証に使用）
export const getNeonJWT = (): Promise<string | null> =>
	_neonAuthInternal.getJWTToken();

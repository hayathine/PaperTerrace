import type React from "react";
import {
	createContext,
	useCallback,
	useContext,
	useEffect,
	useState,
} from "react";
import { authClient } from "@/lib/auth";
import { createLogger } from "@/lib/logger";

const log = createLogger("Auth");

interface AuthContextType {
	user: any | null;
	loading: boolean;
	signInWithGoogle: () => Promise<void>;
	signInWithGithub: () => Promise<void>;
	loginAsGuest: () => void;
	logout: () => Promise<void>;
	token: string | null;
	getToken: (forceRefresh?: boolean) => Promise<string | null>;
	isGuest: boolean;
}

const AuthContext = createContext<AuthContextType | null>(null);

export const useAuth = () => {
	const context = useContext(AuthContext);
	if (!context) throw new Error("useAuth must be used within an AuthProvider");
	return context;
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({
	children,
}) => {
	const [user, setUser] = useState<any | null>(null);
	const [loading, setLoading] = useState(true);
	const [token, setToken] = useState<string | null>(null);
	const [isGuest, setIsGuest] = useState(true);

	// Note: Neon Auth / Better Auth handles sessions primarily via cookies.
	// We use their client state management here.
	const { data: session, isPending } = authClient.useSession();

	useEffect(() => {
		if (!isPending) {
			if (session) {
				setUser(session.user);
				setIsGuest(false);
				// In a real app, you might want to extract a CSRF token or session token
				// if not using HTTP-only cookies for the API.
				setToken(null);
			} else {
				setUser(null);
				setIsGuest(true);
				setToken(null);
			}
			setLoading(false);
		}
	}, [session, isPending]);

	const getToken = useCallback(async (): Promise<string | null> => {
		// For Neon Auth, the backend usually verifies the Session Cookie.
		// If we need a Bearer token, we'd get it from the session.
		return null;
	}, []);

	const signInWithGoogle = async () => {
		try {
			await authClient.signIn.social({ provider: "google" });
		} catch (error) {
			log.error("sign_in_google", "Error signing in with Google", { error });
			throw error;
		}
	};

	const signInWithGithub = async () => {
		try {
			await authClient.signIn.social({ provider: "github" });
		} catch (error) {
			log.error("sign_in_github", "Error signing in with Github", { error });
			throw error;
		}
	};

	const loginAsGuest = () => {
		setIsGuest(true);
	};

	const logout = async () => {
		try {
			await authClient.signOut();
			setUser(null);
			setToken(null);
			setIsGuest(true);
		} catch (error) {
			log.error("logout", "Error signing out", { error });
			throw error;
		}
	};

	return (
		<AuthContext.Provider
			value={{
				user,
				loading,
				signInWithGoogle,
				signInWithGithub,
				loginAsGuest,
				logout,
				token,
				getToken,
				isGuest,
			}}
		>
			{!loading && children}
		</AuthContext.Provider>
	);
};

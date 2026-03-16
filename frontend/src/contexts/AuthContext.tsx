import type React from "react";
import {
	createContext,
	useCallback,
	useContext,
	useEffect,
	useState,
} from "react";
import { API_URL } from "@/config";
import { authClient, getNeonJWT } from "@/lib/auth";
import { createLogger } from "@/lib/logger";

const log = createLogger("Auth");

/** Better Auth / Neon Auth が返すユーザーオブジェクトの型 */
interface AuthUser {
	id: string;
	name: string | null;
	email: string | null;
	image?: string | null;
	emailVerified: boolean;
	createdAt: Date;
	updatedAt: Date;
}

interface AuthContextType {
	user: AuthUser | null;
	loading: boolean;
	signInWithGoogle: () => Promise<void>;
	signInWithGithub: () => Promise<void>;
	signInWithGoogleRedirect: () => Promise<void>;
	signInWithGithubRedirect: () => Promise<void>;
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
	const [user, setUser] = useState<AuthUser | null>(null);
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
				// session.session.token は opaque token のため、JWT を別途取得する
				getNeonJWT()
					.then((jwt) => {
						setToken(jwt);
						// バックエンド DB にユーザーを登録（未登録の場合は新規作成）
						if (jwt) {
							fetch(`${API_URL}/api/auth/register`, {
								method: "POST",
								headers: { Authorization: `Bearer ${jwt}` },
							}).catch((err) => {
								log.error("register", "Failed to register user in backend", {
									err,
								});
							});
						}
					})
					.catch(() => {
						setToken(null);
					})
					.finally(() => {
						setLoading(false);
					});
			} else {
				setUser(null);
				setIsGuest(true);
				setToken(null);
				setLoading(false);
			}
		}
	}, [session, isPending]);

	const getToken = useCallback(async (): Promise<string | null> => {
		return getNeonJWT();
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
				signInWithGoogleRedirect: signInWithGoogle,
				signInWithGithub,
				signInWithGithubRedirect: signInWithGithub,
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

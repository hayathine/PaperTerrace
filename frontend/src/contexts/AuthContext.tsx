import type React from "react";
import {
	createContext,
	useCallback,
	useContext,
	useEffect,
	useState,
} from "react";
import { API_URL } from "@/config";
import { setGA4UserId } from "@/lib/analytics";
import { authClient, getNeonJWT } from "@/lib/auth";
import { createLogger } from "@/lib/logger";

const AppSplash: React.FC = () => (
	<div className="fixed inset-0 flex items-center justify-center bg-white z-50">
		<div className="flex flex-col items-center gap-6">
			<div className="relative">
				<div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-orange-600 to-amber-500 shadow-lg shadow-orange-200 flex items-center justify-center">
					<svg
						className="w-8 h-8 text-white"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
					>
						<path
							strokeLinecap="round"
							strokeLinejoin="round"
							strokeWidth="2"
							d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
						/>
					</svg>
				</div>
				<div className="absolute -bottom-1 -right-1 w-5 h-5 rounded-full border-2 border-white bg-orange-50 flex items-center justify-center">
					<div className="w-3 h-3 rounded-full border-2 border-orange-600 border-t-transparent animate-spin" />
				</div>
			</div>
			<div className="text-center">
				<div className="text-2xl font-black text-slate-800 tracking-tight">
					Paper<span className="text-orange-600">Terrace</span>
				</div>
				<div className="text-xs text-slate-400 font-medium mt-1">
					準備しています...
				</div>
			</div>
		</div>
	</div>
);

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
				setGA4UserId(session.user.id);
				// session.session.token は opaque token のため、JWT を別途取得する
				getNeonJWT()
					.then((jwt) => {
						setToken(jwt);
						// バックエンド DB にユーザーを登録（未登録の場合は新規作成）
						// バックグラウンドで実行し、JWT 取得後すぐに画面を表示する。
						// 失敗時は自動リトライ（コールドスタート対策）。
						if (jwt) {
							const registerWithRetry = async (retries = 3) => {
								for (let i = 0; i < retries; i++) {
									try {
										const res = await fetch(`${API_URL}/api/auth/register`, {
											method: "POST",
											headers: { Authorization: `Bearer ${jwt}` },
										});
										if (res.ok) return;
									} catch (err) {
										if (i < retries - 1) {
											await new Promise((r) => setTimeout(r, 2000 * (i + 1)));
										} else {
											log.error(
												"register",
												"Failed to register user in backend",
												{ err },
											);
										}
									}
								}
							};
							registerWithRetry();
						}
						setLoading(false);
					})
					.catch(() => {
						setToken(null);
						setLoading(false);
					});
			} else {
				setUser(null);
				setIsGuest(true);
				setToken(null);
				setLoading(false);
				setGA4UserId(null);
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
			setGA4UserId(null);
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
			{loading ? <AppSplash /> : children}
		</AuthContext.Provider>
	);
};

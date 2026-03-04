import { setUserId } from "firebase/analytics";
import {
	signOut as firebaseSignOut,
	getIdToken,
	getRedirectResult,
	onAuthStateChanged,
	signInWithPopup,
	signInWithRedirect,
	type User,
} from "firebase/auth";
import type React from "react";
import {
	createContext,
	useCallback,
	useContext,
	useEffect,
	useState,
} from "react";
import { API_URL } from "@/config";
import {
	analytics,
	auth,
	githubProvider,
	googleProvider,
} from "@/lib/firebase";
import { createLogger } from "@/lib/logger";

const log = createLogger("Auth");

interface AuthContextType {
	user: User | null;
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
	const [user, setUser] = useState<User | null>(null);
	const [loading, setLoading] = useState(true);
	const [token, setToken] = useState<string | null>(null);
	const [isGuest, setIsGuest] = useState(true);

	const syncWithBackend = useCallback(async (idToken: string) => {
		try {
			const response = await fetch(`${API_URL}/api/auth/register`, {
				method: "POST",
				headers: {
					Authorization: `Bearer ${idToken}`,
					"Content-Type": "application/json",
				},
			});
			if (!response.ok) {
				log.warn("sync_with_backend", "Backend sync returned non-OK status", {
					status: response.status,
				});
			}
		} catch (error) {
			log.error("sync_with_backend", "Failed to sync user with backend", {
				error,
			});
		}
	}, []);

	const getToken = useCallback(
		async (forceRefresh = false): Promise<string | null> => {
			if (!auth.currentUser) return null;
			try {
				const idToken = await getIdToken(auth.currentUser, forceRefresh);
				setToken(idToken);
				return idToken;
			} catch (error) {
				log.error("get_token", "Error getting token", { error });

				return null;
			}
		},
		[],
	);

	useEffect(() => {
		// Handle redirect results
		getRedirectResult(auth)
			.then((result) => {
				if (result?.user) {
					log.info("redirect_login", "Logged in via redirect", {
						email: result.user.email,
					});
				}
			})
			.catch((error) => {
				log.error("redirect_login", "Error handling redirect result", {
					error,
				});
			});

		const unsubscribe = onAuthStateChanged(auth, async (currentUser) => {
			if (currentUser) {
				try {
					const idToken = await currentUser.getIdToken();
					setToken(idToken);
					setIsGuest(false);
					// Link Firebase Auth UID to GA4 for BigQuery correlation
					if (analytics) {
						setUserId(analytics, currentUser.uid);
					}
					await syncWithBackend(idToken);
				} catch (error) {
					log.error("auth_state_change", "Error in auth state change", {
						error,
					});
				}
			} else {
				setToken(null);
				setIsGuest(true);
				// Clear GA4 user ID on logout
				if (analytics) {
					setUserId(analytics, null);
				}
			}
			setUser(currentUser);
			setLoading(false);
		});

		// Set up token refresh interval (every 50 minutes)
		const refreshInterval = setInterval(
			() => {
				if (auth.currentUser) {
					getToken(true);
				}
			},
			50 * 60 * 1000,
		);

		return () => {
			unsubscribe();
			clearInterval(refreshInterval);
		};
	}, [syncWithBackend, getToken]);

	const signInWithGoogle = async () => {
		try {
			await signInWithPopup(auth, googleProvider);
		} catch (error) {
			log.error("sign_in_google", "Error signing in with Google", { error });

			throw error;
		}
	};

	const signInWithGoogleRedirect = async () => {
		try {
			await signInWithRedirect(auth, googleProvider);
		} catch (error) {
			log.error(
				"sign_in_google_redirect",
				"Error signing in with Google Redirect",
				{ error },
			);

			throw error;
		}
	};

	const signInWithGithub = async () => {
		try {
			await signInWithPopup(auth, githubProvider);
		} catch (error) {
			log.error("sign_in_github", "Error signing in with Github", { error });

			throw error;
		}
	};

	const signInWithGithubRedirect = async () => {
		try {
			await signInWithRedirect(auth, githubProvider);
		} catch (error) {
			log.error(
				"sign_in_github_redirect",
				"Error signing in with Github Redirect",
				{ error },
			);

			throw error;
		}
	};

	const loginAsGuest = () => {
		setIsGuest(true);
	};

	const logout = async () => {
		try {
			await firebaseSignOut(auth);
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
				signInWithGoogleRedirect,
				signInWithGithubRedirect,
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

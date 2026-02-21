/**
 * Firebase Authentication Service for PaperTerrace
 * Handles user authentication with Google and GitHub
 */

import { initializeApp } from "https://www.gstatic.com/firebasejs/10.7.0/firebase-app.js";
import {
	GithubAuthProvider,
	GoogleAuthProvider,
	getAuth,
	onAuthStateChanged,
	signInWithPopup,
	signOut,
} from "https://www.gstatic.com/firebasejs/10.7.0/firebase-auth.js";

// Firebase configuration - read from window.firebaseConfig (injected by backend)
const firebaseConfig = window.firebaseConfig || {
	apiKey: "FILL_ME",
	authDomain: "FILL_ME",
	projectId: "FILL_ME",
	storageBucket: "FILL_ME",
	messagingSenderId: "FILL_ME",
	appId: "FILL_ME",
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);
const auth = getAuth(app);

// Auth providers
const googleProvider = new GoogleAuthProvider();
const githubProvider = new GithubAuthProvider();

// Current user state
let currentUser = null;
let authToken = null;

/**
 * Sign in with Google
 */
async function signInWithGoogle() {
	try {
		const result = await signInWithPopup(auth, googleProvider);
		return result.user;
	} catch (error) {
		console.error("Google sign-in error:", error);
		throw error;
	}
}

/**
 * Sign in with GitHub
 */
async function signInWithGitHub() {
	try {
		const result = await signInWithPopup(auth, githubProvider);
		return result.user;
	} catch (error) {
		console.error("GitHub sign-in error:", error);
		throw error;
	}
}

/**
 * Sign out the current user
 */
async function signOutUser() {
	try {
		await signOut(auth);
		currentUser = null;
		authToken = null;
		updateAuthUI(null);
	} catch (error) {
		console.error("Sign-out error:", error);
		throw error;
	}
}

/**
 * Get the current auth token for API requests
 */
async function getAuthToken() {
	if (currentUser) {
		try {
			authToken = await currentUser.getIdToken();
			return authToken;
		} catch (error) {
			console.error("Error getting auth token:", error);
			return null;
		}
	}
	return null;
}

/**
 * Register user with backend after Firebase auth
 */
async function registerWithBackend() {
	const token = await getAuthToken();
	if (!token) return null;

	try {
		const response = await fetch("/auth/register", {
			method: "POST",
			headers: {
				Authorization: `Bearer ${token}`,
				"Content-Type": "application/json",
			},
		});

		if (!response.ok) {
			throw new Error("Backend registration failed");
		}

		return await response.json();
	} catch (error) {
		console.error("Backend registration error:", error);
		return null;
	}
}

/**
 * Update the UI based on auth state
 */
function updateAuthUI(user) {
	const authSection = document.getElementById("auth-section");
	const userMenu = document.getElementById("user-menu");
	const loginButtons = document.getElementById("login-buttons");

	if (user) {
		// User is signed in
		if (loginButtons) loginButtons.classList.add("hidden");
		if (userMenu) {
			userMenu.classList.remove("hidden");
			const userAvatar = document.getElementById("user-avatar");
			const userName = document.getElementById("user-name");

			if (userAvatar) {
				if (user.photoURL) {
					userAvatar.innerHTML = `<img src="${user.photoURL}" alt="Avatar" class="w-full h-full rounded-full object-cover">`;
				} else {
					userAvatar.textContent = user.email?.charAt(0).toUpperCase() || "U";
				}
			}
			if (userName) {
				userName.textContent =
					user.displayName || user.email?.split("@")[0] || "User";
			}
		}
	} else {
		// User is signed out
		if (loginButtons) loginButtons.classList.remove("hidden");
		if (userMenu) userMenu.classList.add("hidden");
	}
}

/**
 * Show login modal
 */
function showLoginModal() {
	const modal = document.getElementById("login-modal");
	if (modal) {
		modal.classList.remove("hidden");
		modal.classList.add("flex");
	}
}

/**
 * Hide login modal
 */
function hideLoginModal() {
	const modal = document.getElementById("login-modal");
	if (modal) {
		modal.classList.add("hidden");
		modal.classList.remove("flex");
	}
}

/**
 * Initialize auth state listener
 */
function initAuth() {
	onAuthStateChanged(auth, async (user) => {
		currentUser = user;
		updateAuthUI(user);

		if (user) {
			// User just signed in, register with backend
			await registerWithBackend();
			hideLoginModal();
		}
	});
}

// Export functions to global scope for HTML onclick handlers
window.PaperTerraceAuth = {
	signInWithGoogle,
	signInWithGitHub,
	signOutUser,
	getAuthToken,
	showLoginModal,
	hideLoginModal,
	initAuth,
	getCurrentUser: () => currentUser,
};

// Auto-initialize when script loads
document.addEventListener("DOMContentLoaded", initAuth);

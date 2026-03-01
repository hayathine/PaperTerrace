function resolveApiUrl(): string {
	if (!import.meta.env.PROD) {
		// Local dev server: use relative URL (Vite proxy handles routing)
		return "";
	}

	// VITE_API_URL set at build time (e.g. via Cloudflare Pages env vars) takes
	// priority, allowing per-environment overrides without changing source code.
	if (import.meta.env.VITE_API_URL) {
		return import.meta.env.VITE_API_URL as string;
	}

	// Runtime fallback: infer the correct Worker URL from the deployment hostname.
	// paperterrace-dev.pages.dev → dev Worker
	// Any other production host  → main Worker
	const hostname =
		typeof window !== "undefined" ? window.location.hostname : "";
	if (hostname.includes("-dev.pages.dev") || hostname.startsWith("dev.")) {
		// Set VITE_API_URL in the Cloudflare Pages "dev" environment to override this.
		return "https://paperterrace-dev.gwsgsgdas.workers.dev";
	}
	return "https://worker.paperterrace.page";
}

export const API_URL = resolveApiUrl();

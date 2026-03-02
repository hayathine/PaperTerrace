function resolveApiUrl(): string {
	if (!import.meta.env.PROD) {
		return "";
	}

	const hostname =
		typeof window !== "undefined" ? window.location.hostname : "";
	let url = "https://worker.paperterrace.page";

	if (hostname.includes("-dev.pages.dev") || hostname.startsWith("dev.")) {
		url = "https://paperterracedevworker.gwsgsgdas.workers.dev";
	} else if (import.meta.env.VITE_API_URL) {
		url = import.meta.env.VITE_API_URL as string;
	}

	console.log(`[Config] API URL resolved to: ${url} (hostname: ${hostname})`);
	return url;
}

export const API_URL = resolveApiUrl();

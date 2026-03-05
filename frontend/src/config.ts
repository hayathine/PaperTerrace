import { createLogger } from "@/lib/logger";

const log = createLogger("Config");

function resolveApiUrl(): string {
	if (!import.meta.env.PROD) {
		return "";
	}

	const hostname =
		typeof window !== "undefined" ? window.location.hostname : "";
	let url = "https://worker.paperterrace.page";

	if (
		(hostname.includes(".pages.dev") &&
			hostname !== "paperterrace.pages.dev") ||
		hostname.startsWith("dev.") ||
		hostname === "localhost" ||
		hostname === "127.0.0.1"
	) {
		url = "https://paperterracedevworker.gwsgsgdas.workers.dev";
	} else if (import.meta.env.VITE_API_URL) {
		url = import.meta.env.VITE_API_URL as string;
	}

	log.info("resolve_api_url", "API URL resolved", { url, hostname });

	return url;
}

export const API_URL = resolveApiUrl();

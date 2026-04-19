declare global {
	interface Window {
		dataLayer: unknown[];
		gtag: (...args: unknown[]) => void;
	}
}

const MEASUREMENT_ID = import.meta.env.VITE_GA4_MEASUREMENT_ID as
	| string
	| undefined;

export function initGA4(): void {
	if (!MEASUREMENT_ID) return;
	if (typeof window === "undefined") return;
	if (typeof window.gtag === "function") return;

	const script = document.createElement("script");
	script.async = true;
	script.src = `https://www.googletagmanager.com/gtag/js?id=${MEASUREMENT_ID}`;
	document.head.appendChild(script);

	window.dataLayer = window.dataLayer || [];
	window.gtag = function gtag(...args: unknown[]) {
		window.dataLayer.push(args);
	};
	window.gtag("js", new Date());
	window.gtag("config", MEASUREMENT_ID);
}

export function setGA4UserId(userId: string | null): void {
	if (!MEASUREMENT_ID) return;
	if (typeof window === "undefined" || typeof window.gtag !== "function")
		return;

	window.gtag("config", MEASUREMENT_ID, {
		user_id: userId ?? undefined,
	});
}

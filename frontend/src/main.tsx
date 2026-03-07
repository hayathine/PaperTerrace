import * as Sentry from "@sentry/react";
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.tsx";
import { GLITCHTIP_DSN } from "./config";
import { AuthProvider } from "./contexts/AuthContext";
import { LoadingProvider } from "./contexts/LoadingContext";
import { initDB } from "./db/index";
import "./index.css";
import "./lib/i18n";
import { performanceMonitor } from "./lib/performance";

if (GLITCHTIP_DSN) {
	Sentry.init({
		dsn: GLITCHTIP_DSN,
		integrations: [
			Sentry.browserTracingIntegration(),
			Sentry.replayIntegration(),
		],
		tracesSampleRate: 1.0,
		replaysSessionSampleRate: 0.1,
		replaysOnErrorSampleRate: 1.0,
		environment: import.meta.env.MODE,
	});
}

// Initialize IndexedDB early; failures are non-fatal (caching is disabled).
initDB();

// Initialize Web Vitals performance monitoring
performanceMonitor.init();

ReactDOM.createRoot(document.getElementById("root")!).render(
	<React.StrictMode>
		<AuthProvider>
			<LoadingProvider>
				<App />
			</LoadingProvider>
		</AuthProvider>
	</React.StrictMode>,
);

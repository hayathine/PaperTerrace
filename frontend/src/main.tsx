import * as Sentry from "@sentry/react";
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.tsx";
import ErrorBoundary from "./components/Error/ErrorBoundary";
import { GLITCHTIP_DSN, SENTRY_TUNNEL } from "./config";
import { AuthProvider } from "./contexts/AuthContext";
import { LoadingProvider } from "./contexts/LoadingContext";
import { initDB } from "./db/index";
import "./index.css";
import "./lib/i18n";
import { performanceMonitor } from "./lib/performance";

if (GLITCHTIP_DSN) {
	Sentry.init({
		dsn: GLITCHTIP_DSN,
		tunnel: SENTRY_TUNNEL,
		integrations: [Sentry.browserTracingIntegration()],
		tracesSampleRate: 1.0,
		environment: import.meta.env.MODE,
	});
}

// Initialize IndexedDB early; failures are non-fatal (caching is disabled).
initDB();

// Initialize Web Vitals performance monitoring
performanceMonitor.init();

// グローバルエラーハンドラ: React マウント前のクラッシュ（例: 認証SDK初期化失敗）を捕捉して
// メンテナンス画面を表示する。React マウント後は ErrorBoundary が担当する。
let reactMounted = false;
const showStaticMaintenance = () => {
	if (reactMounted) return;
	const root = document.getElementById("root");
	if (root && !root.hasChildNodes()) {
		root.innerHTML = `
			<div style="position:fixed;inset:0;display:flex;align-items:center;justify-content:center;background:rgba(15,23,42,0.4);backdrop-filter:blur(20px);z-index:9999">
				<div style="text-align:center;padding:3rem;max-width:400px;background:rgba(255,255,255,0.85);border-radius:2rem;box-shadow:0 32px 128px -16px rgba(0,0,0,0.3)">
					<div style="font-size:2rem;font-weight:900;color:#1e293b;margin-bottom:0.75rem">メンテナンス中</div>
					<p style="color:#64748b;margin-bottom:1.5rem;line-height:1.6">現在システムを調整中です。しばらく時間をおいてから再度お試しください。</p>
					<button onclick="location.reload()" style="padding:0.75rem 2rem;background:#1e293b;color:white;border:none;border-radius:0.75rem;font-weight:700;cursor:pointer;font-size:0.875rem">再読み込み</button>
				</div>
			</div>`;
	}
};
window.addEventListener("error", showStaticMaintenance);
window.addEventListener("unhandledrejection", showStaticMaintenance);

ReactDOM.createRoot(document.getElementById("root")!).render(
	<React.StrictMode>
		<ErrorBoundary>
			<AuthProvider>
				<LoadingProvider>
					<App />
				</LoadingProvider>
			</AuthProvider>
		</ErrorBoundary>
	</React.StrictMode>,
);

reactMounted = true;

import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.tsx";
import { AuthProvider } from "./contexts/AuthContext";
import { LoadingProvider } from "./contexts/LoadingContext";
import { initDB } from "./db/index";
import "./index.css";
import "./lib/i18n";

// Initialize IndexedDB early; failures are non-fatal (caching is disabled).
initDB();

ReactDOM.createRoot(document.getElementById("root")!).render(
	<React.StrictMode>
		<AuthProvider>
			<LoadingProvider>
				<App />
			</LoadingProvider>
		</AuthProvider>
	</React.StrictMode>,
);

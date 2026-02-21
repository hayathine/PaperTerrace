import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.tsx";
import { AuthProvider } from "./contexts/AuthContext";
import { LoadingProvider } from "./contexts/LoadingContext";
import "./index.css";
import "./lib/i18n";

ReactDOM.createRoot(document.getElementById("root")!).render(
	<React.StrictMode>
		<AuthProvider>
			<LoadingProvider>
				<App />
			</LoadingProvider>
		</AuthProvider>
	</React.StrictMode>,
);

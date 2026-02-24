import path from "node:path";
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// https://vitejs.dev/config/
export default defineConfig({
	plugins: [react()],
	envDir: "../secrets", // Load .env files from secrets directory
	resolve: {
		alias: {
			"@": path.resolve(__dirname, "./src"),
		},
	},
	server: {
		host: true,
		port: 5173,
		proxy: {
			"/api": {
				target: "http://127.0.0.1:8080",
				changeOrigin: true,
			},
			"/auth": {
				target: "http://127.0.0.1:8080",
				changeOrigin: true,
			},
			"/stamps": {
				target: "http://127.0.0.1:8080",
				changeOrigin: true,
			},
			"/analyze-pdf-json": {
				target: "http://127.0.0.1:8080",
				changeOrigin: true,
			},
			"/stream": {
				target: "http://127.0.0.1:8080",
				changeOrigin: true,
			},
			"/note": {
				target: "http://127.0.0.1:8080",
				changeOrigin: true,
			},
			"/explain": {
				target: "http://127.0.0.1:8080",
				changeOrigin: true,
			},
			"/summarize": {
				target: "http://127.0.0.1:8080",
				changeOrigin: true,
			},
			"/research-radar": {
				target: "http://127.0.0.1:8080",
				changeOrigin: true,
			},
			"/critique": {
				target: "http://127.0.0.1:8080",
				changeOrigin: true,
			},
			"/chat": {
				target: "http://127.0.0.1:8080",
				changeOrigin: true,
			},
			"/papers": {
				target: "http://127.0.0.1:8080",
				changeOrigin: true,
			},
			"/explore": {
				target: "http://127.0.0.1:8080",
				changeOrigin: true,
			},
			"/upload": {
				target: "http://127.0.0.1:8080",
				changeOrigin: true,
			},
			"/static": {
				target: "http://127.0.0.1:8080",
				changeOrigin: true,
			},
		},
	},
	test: {
		globals: true,
		environment: "jsdom",
		setupFiles: "./tests/setup.ts",
	},
});

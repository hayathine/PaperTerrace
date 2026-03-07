import { useCallback, useEffect, useRef, useState } from "react";
import { API_URL } from "@/config";
import { createLogger } from "@/lib/logger";

const log = createLogger("useServiceHealth");

const POLL_INTERVAL_UNHEALTHY = 10000;

interface HealthStatus {
	status: "healthy" | "unhealthy" | "maintenance" | "unknown";
	message?: string;
}

export const useServiceHealth = (enabled = true) => {
	const [health, setHealth] = useState<HealthStatus>({ status: "healthy" });
	const healthRef = useRef(health);
	healthRef.current = health;

	const checkHealth = useCallback(async () => {
		try {
			const res = await fetch(`${API_URL}/api/health`, {
				// Short timeout for health check
				signal: AbortSignal.timeout(5000),
			});

			if (res.status === 200) {
				setHealth({ status: "healthy" });
			} else if (res.status === 503) {
				const data = await res.json().catch(() => ({}));
				if (data.status === "maintenance") {
					setHealth({
						status: "maintenance",
						message: data.message,
					});
				} else {
					setHealth({ status: "unhealthy" });
				}
			} else {
				// Other error status (502, 504 etc)
				setHealth({ status: "unhealthy" });
			}
		} catch (err) {
			log.error("check_health", "Failed to reach health endpoint", {
				error: err,
			});
			setHealth({ status: "unhealthy" });
		}
	}, []);

	// Initial check + periodic polling (skip for guest users)
	useEffect(() => {
		if (!enabled) return;

		checkHealth();

		const interval = setInterval(() => {
			const isHealthy = healthRef.current.status === "healthy";
			if (!isHealthy) {
				checkHealth();
			}
		}, POLL_INTERVAL_UNHEALTHY);

		return () => clearInterval(interval);
	}, [checkHealth, enabled]);

	// Global response interceptor simulation:
	// If any fetch fails with 503/504, we immediately trigger a health check
	const reportFailure = useCallback(
		(status: number) => {
			if (status === 502 || status === 503 || status === 504) {
				checkHealth();
			}
		},
		[checkHealth],
	);

	return {
		isHealthy: health.status === "healthy",
		isMaintenance: health.status === "maintenance",
		isUnhealthy: health.status === "unhealthy",
		status: health.status,
		message: health.message,
		checkHealth,
		reportFailure,
	};
};

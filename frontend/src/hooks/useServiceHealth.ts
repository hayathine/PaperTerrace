import { useCallback, useEffect, useState } from "react";
import { API_URL } from "@/config";
import { createLogger } from "@/lib/logger";

const log = createLogger("useServiceHealth");

interface HealthStatus {
	status: "healthy" | "unhealthy" | "maintenance" | "unknown";
	message?: string;
}

export const useServiceHealth = () => {
	const [health, setHealth] = useState<HealthStatus>({ status: "healthy" });

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

	// Initial check and periodic check if unhealthy
	useEffect(() => {
		checkHealth();

		const interval = setInterval(
			() => {
				// Only poll frequently if we are currently unhealthy or maintenance
				if (health.status !== "healthy") {
					checkHealth();
				}
			},
			health.status === "healthy" ? 60000 : 10000,
		); // 60s if healthy, 10s if unhealthy

		return () => clearInterval(interval);
	}, [checkHealth, health.status]);

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

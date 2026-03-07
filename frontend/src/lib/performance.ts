// Web Vitals performance monitoring

import type { Metric } from "web-vitals";
import { onCLS, onFCP, onLCP, onTTFB } from "web-vitals";
import { PERF_FLAGS } from "../config/performance";

interface PerformanceMetric {
	name: string;
	value: number;
	rating: "good" | "needs-improvement" | "poor";
	timestamp: number;
}

class PerformanceMonitor {
	private metrics: PerformanceMetric[] = [];

	init() {
		if (!PERF_FLAGS.performanceMonitoring) return;

		const handler = (metric: Metric) => this.handleMetric(metric);
		onCLS(handler);
		onLCP(handler);
		onFCP(handler);
		onTTFB(handler);
	}

	private handleMetric(metric: Metric) {
		const entry: PerformanceMetric = {
			name: metric.name,
			value: metric.value,
			rating: metric.rating,
			timestamp: Date.now(),
		};

		this.metrics.push(entry);

		if (import.meta.env.DEV) {
			const color =
				metric.rating === "good"
					? "color: green"
					: metric.rating === "needs-improvement"
						? "color: orange"
						: "color: red";
			console.log(
				`%c[Perf] ${metric.name}: ${metric.value.toFixed(1)} (${metric.rating})`,
				color,
			);
		}
	}

	getMetrics(): PerformanceMetric[] {
		return this.metrics;
	}
}

export const performanceMonitor = new PerformanceMonitor();

import { logEvent } from "firebase/analytics";
import { useCallback, useEffect, useRef } from "react";
import { analytics } from "@/lib/firebase";

export const useScrollTracking = (
	paperIdentifier: string | null | undefined,
) => {
	const trackedThresholds = useRef<Set<number>>(new Set());

	// Reset tracked thresholds when paper changes
	useEffect(() => {
		trackedThresholds.current.clear();
	}, [paperIdentifier]);

	const handleScroll = useCallback(
		(e: React.UIEvent<HTMLDivElement>) => {
			if (!analytics || !paperIdentifier) return;

			const target = e.currentTarget;
			const scrollBottom = target.scrollTop + target.clientHeight;
			const scrollHeight = target.scrollHeight;

			// Prevent tracking if content isn't scrollable or just barely scrollable
			if (scrollHeight <= target.clientHeight + 10) return;

			const scrollPercent = Math.round((scrollBottom / scrollHeight) * 100);

			// Define thresholds we want to track
			const thresholds = [10, 25, 50, 75, 90, 100];

			for (const threshold of thresholds) {
				if (
					scrollPercent >= threshold &&
					!trackedThresholds.current.has(threshold)
				) {
					trackedThresholds.current.add(threshold);

					logEvent(analytics, "scroll", {
						percent_scrolled: threshold,
						paper_id: paperIdentifier,
					});
				}
			}
		},
		[paperIdentifier],
	);

	return handleScroll;
};

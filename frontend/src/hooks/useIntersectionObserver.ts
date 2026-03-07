import type { RefObject } from "react";
import { useEffect, useRef, useState } from "react";
import { PERFORMANCE_CONFIG } from "../config/performance";

/**
 * Intersection Observer hook for lazy rendering.
 * Returns true when the observed element is within the viewport (+ margin).
 */
export function useIntersectionObserver(
	ref: RefObject<Element | null>,
	options: IntersectionObserverInit = {},
): boolean {
	const [isIntersecting, setIsIntersecting] = useState(false);
	// Stabilize options to avoid re-creating observer on every render
	const optionsRef = useRef(options);

	useEffect(() => {
		const element = ref.current;
		if (!element) return;

		const observer = new IntersectionObserver(
			([entry]) => {
				setIsIntersecting(entry.isIntersecting);
			},
			{
				rootMargin: PERFORMANCE_CONFIG.intersectionObserver.rootMargin,
				threshold: PERFORMANCE_CONFIG.intersectionObserver.threshold,
				...optionsRef.current,
			},
		);

		observer.observe(element);
		return () => observer.disconnect();
	}, [ref]);

	return isIntersecting;
}

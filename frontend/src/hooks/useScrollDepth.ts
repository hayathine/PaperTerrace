import { type RefObject, useEffect, useRef } from "react";

declare function gtag(
	command: string,
	eventName: string,
	params: Record<string, unknown>,
): void;

/**
 * スクロール深度を 25/50/75/90% のしきい値で GA4 に送信するフック。
 * containerRef を渡せばその要素内のスクロールを、省略した場合は window を監視する。
 */
export function useScrollDepth(
	paperIdentifier: string | null | undefined,
	containerRef?: RefObject<HTMLElement>,
) {
	const trackedThresholds = useRef<Set<number>>(new Set());

	// 論文が切り替わったら追跡済みしきい値をリセット
	useEffect(() => {
		trackedThresholds.current.clear();
	}, [paperIdentifier]);

	useEffect(() => {
		if (!paperIdentifier) return;

		const thresholds = [25, 50, 75, 90];

		const getScrollInfo = () => {
			const target = containerRef?.current;
			if (target) {
				return {
					scrollBottom: target.scrollTop + target.clientHeight,
					scrollHeight: target.scrollHeight,
					clientHeight: target.clientHeight,
				};
			}
			return {
				scrollBottom: window.scrollY + window.innerHeight,
				scrollHeight: document.documentElement.scrollHeight,
				clientHeight: window.innerHeight,
			};
		};

		const handleScroll = () => {
			const { scrollBottom, scrollHeight, clientHeight } = getScrollInfo();
			if (scrollHeight <= clientHeight + 10) return;

			const scrollPercent = Math.round((scrollBottom / scrollHeight) * 100);

			for (const threshold of thresholds) {
				if (
					scrollPercent >= threshold &&
					!trackedThresholds.current.has(threshold)
				) {
					trackedThresholds.current.add(threshold);
					if (typeof gtag !== "undefined") {
						gtag("event", "scroll_depth", {
							threshold_percent: threshold,
							paper_id: paperIdentifier,
						});
					}
				}
			}
		};

		const target = containerRef?.current;
		if (target) {
			target.addEventListener("scroll", handleScroll, { passive: true });
			return () => target.removeEventListener("scroll", handleScroll);
		}
		window.addEventListener("scroll", handleScroll, { passive: true });
		return () => window.removeEventListener("scroll", handleScroll);
	}, [paperIdentifier, containerRef]);
}

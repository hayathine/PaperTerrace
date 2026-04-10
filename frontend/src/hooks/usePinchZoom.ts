import { useCallback, useEffect, useRef, useState } from "react";

interface UsePinchZoomOptions {
	min?: number;
	max?: number;
	wheelStep?: number;
}

interface UsePinchZoomReturn {
	zoom: number;
	resetZoom: () => void;
	zoomIn: () => void;
	zoomOut: () => void;
	containerRef: React.RefObject<HTMLDivElement>;
	onWheel: (e: React.WheelEvent) => void;
}

/**
 * ピンチズーム（タッチ）と Ctrl+ホイール（デスクトップ）によるズーム制御フック。
 * ポインターイベントを直接 DOM に登録し、ピンチ中は preventDefault() でブラウザのデフォルト動作を抑制する。
 */
export function usePinchZoom({
	min = 1,
	max = 4,
	wheelStep = 0.05,
}: UsePinchZoomOptions = {}): UsePinchZoomReturn {
	const [zoom, setZoom] = useState(1);
	const containerRef = useRef<HTMLDivElement>(null);

	// ピンチ追跡用
	const pointersRef = useRef<Map<number, { x: number; y: number }>>(new Map());
	const lastPinchDistRef = useRef<number | null>(null);

	const clamp = (v: number) => Math.min(max, Math.max(min, v));

	const resetZoom = useCallback(() => setZoom(1), []);
	const zoomIn = useCallback(
		() => setZoom((prev) => clamp(Math.round((prev + wheelStep) * 100) / 100)),
		[wheelStep, min, max],
	);
	const zoomOut = useCallback(
		() => setZoom((prev) => clamp(Math.round((prev - wheelStep) * 100) / 100)),
		[wheelStep, min, max],
	);

	// ポインターイベントで pinch zoom を検出（passive: false で preventDefault 可能）
	useEffect(() => {
		const el = containerRef.current;
		if (!el) return;

		const getDistance = (
			p1: { x: number; y: number },
			p2: { x: number; y: number },
		) => Math.hypot(p1.x - p2.x, p1.y - p2.y);

		const onPointerDown = (e: PointerEvent) => {
			pointersRef.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
		};

		const onPointerMove = (e: PointerEvent) => {
			if (!pointersRef.current.has(e.pointerId)) return;
			pointersRef.current.set(e.pointerId, { x: e.clientX, y: e.clientY });

			if (pointersRef.current.size === 2) {
				const [p1, p2] = [...pointersRef.current.values()];
				const dist = getDistance(p1, p2);

				if (lastPinchDistRef.current !== null) {
					const ratio = dist / lastPinchDistRef.current;
					setZoom((prev) => clamp(prev * ratio));
				}
				lastPinchDistRef.current = dist;
				// ブラウザのネイティブ pinch zoom / scroll を抑制
				e.preventDefault();
			}
		};

		const onPointerUp = (e: PointerEvent) => {
			pointersRef.current.delete(e.pointerId);
			if (pointersRef.current.size < 2) {
				lastPinchDistRef.current = null;
			}
		};

		el.addEventListener("pointerdown", onPointerDown);
		el.addEventListener("pointermove", onPointerMove, { passive: false });
		el.addEventListener("pointerup", onPointerUp);
		el.addEventListener("pointercancel", onPointerUp);

		return () => {
			el.removeEventListener("pointerdown", onPointerDown);
			el.removeEventListener("pointermove", onPointerMove);
			el.removeEventListener("pointerup", onPointerUp);
			el.removeEventListener("pointercancel", onPointerUp);
		};
	}, [min, max]);

	// Ctrl+ホイール でデスクトップズーム
	const onWheel = useCallback(
		(e: React.WheelEvent) => {
			if (!e.ctrlKey) return;
			e.preventDefault();
			const delta = e.deltaY > 0 ? -wheelStep : wheelStep;
			setZoom((prev) => clamp(prev + delta));
		},
		[wheelStep, min, max],
	);

	return { zoom, resetZoom, zoomIn, zoomOut, containerRef, onWheel };
}

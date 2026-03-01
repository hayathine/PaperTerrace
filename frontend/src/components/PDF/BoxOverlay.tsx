import type React from "react";
import { useCallback, useEffect, useRef, useState } from "react";

interface BoxOverlayProps {
	isActive: boolean;
	onSelect: (rect: {
		x: number;
		y: number;
		width: number;
		height: number;
	}) => void;
}

const BoxOverlay: React.FC<BoxOverlayProps> = ({ isActive, onSelect }) => {
	const [start, setStart] = useState<{ x: number; y: number } | null>(null);
	const [current, setCurrent] = useState<{ x: number; y: number } | null>(null);
	const containerRef = useRef<HTMLDivElement>(null);

	useEffect(() => {
		if (!isActive) {
			setStart(null);
			setCurrent(null);
		}
	}, [isActive]);

	// Shared coordinate calculator: converts client position to container-relative [0-1] coords
	const getRelativeCoordsFromClient = useCallback(
		(clientX: number, clientY: number) => {
			if (!containerRef.current) return { x: 0, y: 0 };
			const rect = containerRef.current.getBoundingClientRect();
			return {
				x: Math.max(0, Math.min(1, (clientX - rect.left) / rect.width)),
				y: Math.max(0, Math.min(1, (clientY - rect.top) / rect.height)),
			};
		},
		[],
	);

	// Track mouse/touch events globally so drags outside the overlay are handled correctly
	useEffect(() => {
		if (!start) return;

		const finishSelection = (end: { x: number; y: number }) => {
			const x = Math.min(start.x, end.x);
			const y = Math.min(start.y, end.y);
			const w = Math.abs(end.x - start.x);
			const h = Math.abs(end.y - start.y);

			// Only trigger if size is significant (> 1% of dimension)
			if (w > 0.01 && h > 0.01) {
				onSelect({ x, y, width: w, height: h });
			}

			setStart(null);
			setCurrent(null);
		};

		const handleWindowMouseMove = (e: MouseEvent) => {
			setCurrent(getRelativeCoordsFromClient(e.clientX, e.clientY));
		};

		const handleWindowMouseUp = (e: MouseEvent) => {
			finishSelection(getRelativeCoordsFromClient(e.clientX, e.clientY));
		};

		const handleWindowTouchMove = (e: TouchEvent) => {
			// Prevent scroll while drawing a crop selection
			e.preventDefault();
			const touch = e.touches[0];
			setCurrent(getRelativeCoordsFromClient(touch.clientX, touch.clientY));
		};

		const handleWindowTouchEnd = (e: TouchEvent) => {
			const touch = e.changedTouches[0];
			finishSelection(
				getRelativeCoordsFromClient(touch.clientX, touch.clientY),
			);
		};

		window.addEventListener("mousemove", handleWindowMouseMove);
		window.addEventListener("mouseup", handleWindowMouseUp);
		window.addEventListener("touchmove", handleWindowTouchMove, {
			passive: false,
		});
		window.addEventListener("touchend", handleWindowTouchEnd);

		return () => {
			window.removeEventListener("mousemove", handleWindowMouseMove);
			window.removeEventListener("mouseup", handleWindowMouseUp);
			window.removeEventListener("touchmove", handleWindowTouchMove);
			window.removeEventListener("touchend", handleWindowTouchEnd);
		};
	}, [start, onSelect, getRelativeCoordsFromClient]);

	if (!isActive) return null;

	const handleMouseDown = (e: React.MouseEvent) => {
		e.preventDefault();
		const coords = getRelativeCoordsFromClient(e.clientX, e.clientY);
		setStart(coords);
		setCurrent(coords);
	};

	const handleTouchStart = (e: React.TouchEvent) => {
		// Prevent scroll/zoom when initiating a crop selection
		e.preventDefault();
		const touch = e.touches[0];
		const coords = getRelativeCoordsFromClient(touch.clientX, touch.clientY);
		setStart(coords);
		setCurrent(coords);
	};

	// Calculate style for selection box
	let boxStyle = {};
	if (start && current) {
		const x = Math.min(start.x, current.x);
		const y = Math.min(start.y, current.y);
		const w = Math.abs(current.x - start.x);
		const h = Math.abs(current.y - start.y);

		boxStyle = {
			left: `${x * 100}%`,
			top: `${y * 100}%`,
			width: `${w * 100}%`,
			height: `${h * 100}%`,
		};
	}

	return (
		<section
			aria-label="Selection overlay"
			ref={containerRef}
			className="absolute inset-0 z-50 cursor-crosshair select-none"
			onMouseDown={handleMouseDown}
			onTouchStart={handleTouchStart}
			onKeyDown={() => {
				// Keyboard support could be added here if needed
			}}
		>
			{start && current && (
				<div
					className="absolute border-2 border-orange-500 bg-orange-200/30 backdrop-blur-sm pointer-events-none"
					style={boxStyle}
				/>
			)}
		</section>
	);
};

export default BoxOverlay;

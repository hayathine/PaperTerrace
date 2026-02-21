import type React from "react";
import { useEffect, useRef, useState } from "react";

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

	if (!isActive) return null;

	const getRelativeCoords = (e: React.MouseEvent) => {
		if (!containerRef.current) return { x: 0, y: 0 };
		const rect = containerRef.current.getBoundingClientRect();
		return {
			x: (e.clientX - rect.left) / rect.width,
			y: (e.clientY - rect.top) / rect.height,
		};
	};

	const handleMouseDown = (e: React.MouseEvent) => {
		e.preventDefault();
		const coords = getRelativeCoords(e);
		setStart(coords);
		setCurrent(coords);
	};

	const handleMouseMove = (e: React.MouseEvent) => {
		if (!start) return;
		e.preventDefault();
		setCurrent(getRelativeCoords(e));
	};

	const handleMouseUp = (e: React.MouseEvent) => {
		if (!start || !current) return;

		const end = getRelativeCoords(e);

		// Calculate normalized rect
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
		<div
			ref={containerRef}
			className="absolute inset-0 z-50 cursor-crosshair select-none"
			onMouseDown={handleMouseDown}
			onMouseMove={handleMouseMove}
			onMouseUp={handleMouseUp}
			onMouseLeave={() => {
				setStart(null);
				setCurrent(null);
			}}
		>
			{start && current && (
				<div
					className="absolute border-2 border-indigo-500 bg-indigo-200/30 backdrop-blur-sm pointer-events-none"
					style={boxStyle}
				/>
			)}
		</div>
	);
};

export default BoxOverlay;

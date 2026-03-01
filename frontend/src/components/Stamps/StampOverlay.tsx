import type React from "react";
import type { Stamp } from "./types";

interface StampOverlayProps {
	stamps: Stamp[];
	isStampMode: boolean;
	onAddStamp: (x: number, y: number) => void;
	onDeleteStamp?: (stampId: string) => void;
}

const StampOverlay: React.FC<StampOverlayProps> = ({
	stamps,
	isStampMode,
	onAddStamp,
	onDeleteStamp,
}) => {
	const handleClick = (e: React.MouseEvent<HTMLElement>) => {
		if (!isStampMode || !e.currentTarget) return;

		// Calculate percentage coordinates
		const rect = e.currentTarget.getBoundingClientRect();
		const x = ((e.clientX - rect.left) / rect.width) * 100;
		const y = ((e.clientY - rect.top) / rect.height) * 100;

		onAddStamp(x, y);
	};

	return (
		<button
			type="button"
			tabIndex={isStampMode ? 0 : -1}
			aria-label="Add stamp overlay"
			className={`absolute inset-0 w-full h-full z-20 ${isStampMode ? "cursor-crosshair overflow-hidden" : "pointer-events-none"} bg-transparent border-none p-0`}
			onClick={handleClick}
			onKeyDown={(e) => {
				if (e.key === "Enter" || e.key === " ") {
					// Default to center if no mouse position
					onAddStamp(50, 50);
				}
			}}
		>
			{stamps.map((stamp) => (
				// biome-ignore lint/a11y/noStaticElementInteractions: stamp div is inside a button; role="button" nesting is invalid HTML, so we use div with keyboard handler
				<div
					key={stamp.id}
					className="absolute text-2xl animate-stamp-pop select-none transform -translate-x-1/2 -translate-y-1/2 drop-shadow-md hover:scale-125 transition-transform cursor-pointer pointer-events-auto"
					style={{
						left: `${stamp.x}%`,
						top: `${stamp.y}%`,
					}}
					title={`Stamp: ${stamp.type} (Right-click to delete)`}
					onClick={(e) => e.stopPropagation()}
					onKeyDown={(e) => {
						if (e.key === "Delete" || e.key === "Backspace") {
							e.stopPropagation();
							if (onDeleteStamp) onDeleteStamp(stamp.id);
						}
					}}
					onContextMenu={(e) => {
						e.preventDefault();
						e.stopPropagation();
						if (onDeleteStamp) onDeleteStamp(stamp.id);
					}}
				>
					{stamp.type.startsWith("/") ||
					stamp.type.startsWith("http") ||
					stamp.type.startsWith("data:image") ? (
						<img
							src={stamp.type}
							alt="stamp"
							className="w-8 h-8 object-contain pointer-events-none drop-shadow-md"
						/>
					) : (
						stamp.type
					)}
				</div>
			))}
		</button>
	);
};

export default StampOverlay;

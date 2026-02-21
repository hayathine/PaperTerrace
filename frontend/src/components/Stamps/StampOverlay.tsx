import React from "react";
import { Stamp } from "./types";

interface StampOverlayProps {
  stamps: Stamp[];
  isStampMode: boolean;
  onAddStamp: (x: number, y: number) => void;
}

const StampOverlay: React.FC<StampOverlayProps> = ({
  stamps,
  isStampMode,
  onAddStamp,
}) => {
  const handleClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!isStampMode || !e.currentTarget) return;

    // Calculate percentage coordinates
    const rect = e.currentTarget.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 100;
    const y = ((e.clientY - rect.top) / rect.height) * 100;

    onAddStamp(x, y);
  };

  return (
    <div
      className={`absolute inset-0 w-full h-full z-20 ${isStampMode ? "cursor-crosshair" : "pointer-events-none"}`}
      onClick={handleClick}
    >
      {stamps.map((stamp) => (
        <div
          key={stamp.id}
          className="absolute text-2xl animate-stamp-pop select-none transform -translate-x-1/2 -translate-y-1/2 drop-shadow-md hover:scale-125 transition-transform cursor-pointer pointer-events-auto"
          style={{
            left: `${stamp.x}%`,
            top: `${stamp.y}%`,
          }}
          title={`Stamp: ${stamp.type}`}
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
    </div>
  );
};

export default StampOverlay;

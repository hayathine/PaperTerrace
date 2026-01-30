import React from 'react';
import { Stamp } from './types';

interface StampOverlayProps {
    stamps: Stamp[];
    isStampMode: boolean;
    onAddStamp: (x: number, y: number) => void;
}

const StampOverlay: React.FC<StampOverlayProps> = ({ stamps, isStampMode, onAddStamp }) => {

    const handleClick = (e: React.MouseEvent<HTMLDivElement>) => {
        if (!isStampMode) return;

        // Calculate percentage coordinates
        const rect = e.currentTarget.getBoundingClientRect();
        const x = ((e.clientX - rect.left) / rect.width) * 100;
        const y = ((e.clientY - rect.top) / rect.height) * 100;

        onAddStamp(x, y);
    };

    return (
        <div
            className={`absolute inset-0 w-full h-full z-20 ${isStampMode ? 'cursor-crosshair' : 'pointer-events-none'}`}
            onClick={handleClick}
        >
            {stamps.map((stamp) => (
                <div
                    key={stamp.id}
                    className="absolute text-2xl animate-bounce-short select-none transform -translate-x-1/2 -translate-y-1/2 drop-shadow-md hover:scale-125 transition-transform cursor-pointer pointer-events-auto"
                    style={{
                        left: `${stamp.x}%`,
                        top: `${stamp.y}%`
                    }}
                    title={`Stamp: ${stamp.type}`}
                >
                    {stamp.type}
                </div>
            ))}
        </div>
    );
};

export default StampOverlay;

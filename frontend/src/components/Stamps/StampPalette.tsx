import React from 'react';
import { STAMP_TYPES, StampType } from './types';

interface StampPaletteProps {
    isStampMode: boolean;
    onToggleMode: () => void;
    selectedStamp: StampType;
    onSelectStamp: (stamp: StampType) => void;
}

const StampPalette: React.FC<StampPaletteProps> = ({
    isStampMode,
    onToggleMode,
    selectedStamp,
    onSelectStamp
}) => {
    return (
        <div className="fixed bottom-8 left-1/2 transform -translate-x-1/2 z-50 flex flex-col items-center gap-4">
            {/* Main Toggle Button */}
            <button
                onClick={onToggleMode}
                className={`px-6 py-3 rounded-full shadow-lg font-bold transition-all transform hover:scale-105 flex items-center gap-2
                    ${isStampMode ? 'bg-indigo-600 text-white ring-4 ring-indigo-200' : 'bg-white text-slate-700 hover:bg-slate-50'}
                `}
            >
                <span>{isStampMode ? '✨ Stamp Mode ON' : '👍 Stamps'}</span>
            </button>

            {/* Palette */}
            <div className={`
                bg-white rounded-full shadow-2xl border border-slate-200 p-2 flex space-x-2 transition-all duration-300
                ${isStampMode ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8 pointer-events-none'}
            `}>
                {STAMP_TYPES.map(s => (
                    <button
                        key={s}
                        onClick={() => onSelectStamp(s)}
                        className={`
                            w-10 h-10 rounded-full flex items-center justify-center text-lg transition-transform hover:bg-slate-100
                            ${s === selectedStamp ? 'bg-indigo-100 ring-2 ring-indigo-300 scale-110' : ''}
                        `}
                    >
                        {s}
                    </button>
                ))}
            </div>
        </div>
    );
};

export default StampPalette;

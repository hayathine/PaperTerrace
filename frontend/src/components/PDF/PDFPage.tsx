import React, { useMemo } from 'react';
import { PageData } from './types';
import StampOverlay from '../Stamps/StampOverlay';
import BoxOverlay from './BoxOverlay';
import { Stamp } from '../Stamps/types';

interface PDFPageProps {
    page: PageData;
    scale?: number;
    onWordClick?: (word: string, context?: string, coords?: { page: number, x: number, y: number }) => void;
    onTextSelect?: (text: string, coords: { page: number, x: number, y: number }) => void;
    // Stamp props
    stamps?: Stamp[];
    isStampMode?: boolean;
    onAddStamp?: (page: number, x: number, y: number) => void;
    // Area selection props
    isAreaMode?: boolean;
    onAreaSelect?: (coords: { page: number, x: number, y: number, width: number, height: number }) => void;
}

const PDFPage: React.FC<PDFPageProps> = ({
    page,
    onWordClick,
    onTextSelect,
    stamps = [],
    isStampMode = false,
    onAddStamp,
    isAreaMode = false,
    onAreaSelect
}) => {
    const { width, height, words, image_url, page_num } = page;

    // Handle text selection


    const handleMouseUp = (e: React.MouseEvent) => {
        if (isStampMode) return;

        // Wait next tick for selection to populate
        setTimeout(() => {
            const selection = window.getSelection();
            if (!selection || selection.isCollapsed) return;

            const text = selection.toString().trim();
            if (text && onTextSelect) {
                const range = selection.getRangeAt(0);
                const rect = range.getBoundingClientRect();
                const pageEl = e.currentTarget.getBoundingClientRect();

                // Calculate relative coordinates (center of selection)
                const relX = ((rect.left + rect.width / 2) - pageEl.left) / pageEl.width;
                const relY = ((rect.top + rect.height / 2) - pageEl.top) / pageEl.height;

                if (relX >= 0 && relX <= 1 && relY >= 0 && relY <= 1) {
                    onTextSelect(text, { page: page_num, x: relX, y: relY });
                }
            }
        }, 10);
    };

    // Filter stamps for this page
    const pageStamps = useMemo(() => {
        return stamps.filter(s => s.page_number === page_num || !s.page_number);
    }, [stamps, page_num]);

    const handleAddStamp = (x: number, y: number) => {
        if (onAddStamp) {
            onAddStamp(page_num, x, y);
        }
    };

    return (
        <div
            id={`page-${page.page_num}`}
            className="relative mb-8 shadow-2xl rounded-xl overflow-hidden bg-white transition-all duration-300 border border-slate-200/50 mx-auto"
            style={{ maxWidth: '100%' }}
            onMouseUp={handleMouseUp}
        >
            {/* Header / Page Number */}
            <div className="bg-gray-50 border-b border-gray-100 px-4 py-2 flex justify-between items-center">
                <span className="text-xs font-bold text-gray-400 uppercase tracking-widest">
                    Page {page.page_num}
                </span>
            </div>

            {/* Image Container */}
            <div className="relative w-full">
                <img
                    src={image_url}
                    alt={`Page ${page.page_num}`}
                    className="w-full h-auto block select-none"
                    loading="lazy"
                />

                {/* Stamp Overlay */}
                <StampOverlay
                    stamps={pageStamps}
                    isStampMode={isStampMode}
                    onAddStamp={handleAddStamp}
                />

                {/* Box Selection Overlay */}
                <BoxOverlay
                    isActive={isAreaMode}
                    onSelect={(rect) => {
                        if (onAreaSelect) {
                            onAreaSelect({
                                page: page_num,
                                x: rect.x,
                                y: rect.y,
                                width: rect.width,
                                height: rect.height
                            });
                        }
                    }}
                />

                {/* Word Overlays */}
                <div className="absolute inset-0 w-full h-full z-10">
                    {words.map((w, idx) => {
                        const [x1, y1, x2, y2] = w.bbox;
                        const w_width = x2 - x1;
                        const w_height = y2 - y1;

                        const left = (x1 / width) * 100;
                        const top = (y1 / height) * 100;
                        const styleW = (w_width / width) * 100;
                        const styleH = (w_height / height) * 100;

                        return (
                            <div
                                key={`${idx}`}
                                className={`absolute rounded-sm group ${!isStampMode ? 'cursor-pointer hover:bg-yellow-300/30' : 'pointer-events-none'}`}
                                style={{
                                    left: `${left}%`,
                                    top: `${top}%`,
                                    width: `${styleW}%`,
                                    height: `${styleH}%`,
                                }}
                                onClick={() => {
                                    if (!isStampMode && onWordClick) {
                                        const start = Math.max(0, idx - 50);
                                        const end = Math.min(words.length, idx + 50);
                                        const context = words.slice(start, end).map(w => w.word).join(' ');

                                        // Calculate normalized center coordinates
                                        const centerX = (x1 + x2) / 2 / width;
                                        const centerY = (y1 + y2) / 2 / height;

                                        const cleanWord = w.word.replace(/^[.,;!?(){}[\]"']+|[.,;!?(){}[\]"']+$/g, '');
                                        onWordClick(cleanWord, context, { page: page_num, x: centerX, y: centerY });
                                    }
                                }}
                                title={w.word}
                            />
                        );
                    })}
                </div>
            </div>
        </div>
    );
};

export default PDFPage;

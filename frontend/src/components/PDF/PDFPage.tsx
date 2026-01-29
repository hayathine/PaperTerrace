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

    // Text Selection State
    const [isDragging, setIsDragging] = React.useState(false);
    const [selectionStart, setSelectionStart] = React.useState<number | null>(null);
    const [selectionEnd, setSelectionEnd] = React.useState<number | null>(null);

    const handleMouseUp = () => {
        if (isStampMode || isAreaMode) return;

        if (isDragging && selectionStart !== null && selectionEnd !== null) {
            setIsDragging(false);

            if (selectionStart !== selectionEnd) {
                // Multi-word selection -> Note
                if (onTextSelect) {
                    const min = Math.min(selectionStart, selectionEnd);
                    const max = Math.max(selectionStart, selectionEnd);
                    const selectedWords = words.slice(min, max + 1);
                    const text = selectedWords.map(w => w.word).join(' ');

                    // Calculate bounding box of selection for anchor
                    const firstWord = words[min];
                    const lastWord = words[max];
                    const x1 = firstWord.bbox[0];
                    const y1 = firstWord.bbox[1];
                    const x2 = lastWord.bbox[2];
                    const y2 = lastWord.bbox[3];

                    // Center of selection
                    const centerX = (x1 + x2) / 2 / width;
                    const centerY = (y1 + y2) / 2 / height;

                    onTextSelect(text, { page: page_num, x: centerX, y: centerY });
                }
            } else {
                // Single click -> handled by onClick of the div, but we need to ensure not to duplicate
                // Actually, if we use OnClick on the div, it fires after mouseup.
                // We'll let the OnClick handler do the Dictionary lookup.
            }

            // Clear selection after a short delay so user sees what they selected
            setTimeout(() => {
                setSelectionStart(null);
                setSelectionEnd(null);
            }, 300);
        }
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
            onMouseLeave={() => {
                if (isDragging) {
                    setIsDragging(false);
                    setSelectionStart(null);
                    setSelectionEnd(null);
                }
            }}
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

                        const isSelected = selectionStart !== null && selectionEnd !== null &&
                            ((idx >= selectionStart && idx <= selectionEnd) || (idx >= selectionEnd && idx <= selectionStart));

                        return (
                            <div
                                key={`${idx}`}
                                className={`absolute rounded-sm group ${!isStampMode ? 'cursor-pointer' : 'pointer-events-none'} 
                                    ${!isStampMode && !isSelected ? 'hover:bg-yellow-300/30' : ''} 
                                    ${isSelected ? 'bg-indigo-500/30 border border-indigo-500/50' : ''}`}
                                style={{
                                    left: `${left}%`,
                                    top: `${top}%`,
                                    width: `${styleW}%`,
                                    height: `${styleH}%`,
                                }}
                                onMouseDown={(e) => {
                                    if (isStampMode || isAreaMode) return;
                                    // Prevent default text selection
                                    e.preventDefault();
                                    e.stopPropagation();
                                    setIsDragging(true);
                                    setSelectionStart(idx);
                                    setSelectionEnd(idx);
                                }}
                                onMouseEnter={() => {
                                    if (isDragging && selectionStart !== null) {
                                        setSelectionEnd(idx);
                                    }
                                }}
                                onClick={() => {
                                    if (!isStampMode && onWordClick) {
                                        // Only if it was a click (not a drag)
                                        if (selectionStart === selectionEnd) {
                                            const start = Math.max(0, idx - 50);
                                            const end = Math.min(words.length, idx + 50);
                                            const context = words.slice(start, end).map(w => w.word).join(' ');

                                            // Calculate normalized center coordinates
                                            const centerX = (x1 + x2) / 2 / width;
                                            const centerY = (y1 + y2) / 2 / height;

                                            const cleanWord = w.word.replace(/^[.,;!?(){}[\]"']+|[.,;!?(){}[\]"']+$/g, '');
                                            onWordClick(cleanWord, context, { page: page_num, x: centerX, y: centerY });
                                        }
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

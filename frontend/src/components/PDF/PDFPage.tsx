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
    onAskAI?: (prompt: string) => void;
}

const PDFPage: React.FC<PDFPageProps> = ({
    page,
    onWordClick,
    onTextSelect,
    stamps = [],
    isStampMode = false,
    onAddStamp,
    isAreaMode = false,
    onAreaSelect,
    onAskAI
}) => {
    const { width, height, words, figures, image_url, page_num } = page;

    // Text Selection State
    const [isDragging, setIsDragging] = React.useState(false);
    const [selectionStart, setSelectionStart] = React.useState<number | null>(null);
    const [selectionEnd, setSelectionEnd] = React.useState<number | null>(null);
    const [selectionMenu, setSelectionMenu] = React.useState<{ x: number, y: number, text: string, context: string, coords: any } | null>(null);

    const handleMouseUp = () => {
        if (isStampMode || isAreaMode) return;

        if (isDragging && selectionStart !== null && selectionEnd !== null) {
            setIsDragging(false);

            if (selectionStart !== selectionEnd) {
                // Multi-word selection -> Show Menu
                const min = Math.min(selectionStart, selectionEnd);
                const max = Math.max(selectionStart, selectionEnd);
                const selectedWords = words.slice(min, max + 1);
                const text = selectedWords.map(w => w.word).join(' ');
                // Context: grab a bit more surrounding text? For now just the selected text as context + some padding
                const startCtx = Math.max(0, min - 10);
                const endCtx = Math.min(words.length, max + 10);
                const context = words.slice(startCtx, endCtx).map(w => w.word).join(' ');

                // Calculate bounding box of selection for anchor

                // Position menu near the end of selection or center? Center is better.
                // We need pixel coordinates for the menu relative to the page container
                // bbox is [x1, y1, x2, y2] in PDF coordinates (unscaled if width/height match PDF)
                // BUT the words bbox in PageData are likely consistent with width/height.
                // In the render, we use percentages.
                // We want the menu to be absolute positioned in the div.
                // x1, y1 etc are relative to page 'width' and 'height'.

                // Let's use % for position
                const x1 = Math.min(...selectedWords.map(w => w.bbox[0]));
                const y1 = Math.min(...selectedWords.map(w => w.bbox[1]));
                const x2 = Math.max(...selectedWords.map(w => w.bbox[2]));
                const y2 = Math.max(...selectedWords.map(w => w.bbox[3]));

                const centerPctX = ((x1 + x2) / 2 / width) * 100;
                // Place it slightly above the selection
                const topPctY = (y1 / height) * 100;

                const centerX = (x1 + x2) / 2 / width;
                const centerY = (y1 + y2) / 2 / height;

                setSelectionMenu({
                    x: centerPctX,
                    y: topPctY,
                    text,
                    context,
                    coords: { page: page_num, x: centerX, y: centerY }
                });

            } else {
                // Single click
                setSelectionStart(null);
                setSelectionEnd(null);
            }
        }
    };

    // Additional helper to clear selection on outside click
    React.useEffect(() => {
        const handleClickOutside = () => {
            if (selectionMenu) {
                setSelectionMenu(null);
                setSelectionStart(null);
                setSelectionEnd(null);
            }
        };

        if (selectionMenu) {
            document.addEventListener('mousedown', handleClickOutside);
        }
        return () => {
            document.removeEventListener('mousedown', handleClickOutside);
        }
    }, [selectionMenu]);

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
                                    e.preventDefault();
                                    e.stopPropagation();
                                    setIsDragging(true);
                                    setSelectionStart(idx);
                                    setSelectionEnd(idx);
                                    setSelectionMenu(null); // Hide menu on new select start
                                }}
                                onMouseEnter={() => {
                                    if (isDragging && selectionStart !== null) {
                                        setSelectionEnd(idx);
                                    }
                                }}
                                onClick={(e) => {
                                    e.stopPropagation(); // Stop propagation to document
                                    if (!isStampMode && onWordClick) {
                                        if (selectionStart === selectionEnd && !selectionMenu) {
                                            const start = Math.max(0, idx - 50);
                                            const end = Math.min(words.length, idx + 50);
                                            const context = words.slice(start, end).map(w => w.word).join(' ');

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
                
                {/* Figure/Equation Overlays */}
                <div className="absolute inset-0 w-full h-full z-20 pointer-events-none">
                    {figures?.map((fig, idx) => {
                        const [x1, y1, x2, y2] = fig.bbox;
                        // Avoid rendering empty bboxes (like [0,0,0,0] from some native extractions)
                        if (x1 === 0 && y1 === 0 && x2 === 0 && y2 === 0) return null;

                        const f_width = x2 - x1;
                        const f_height = y2 - y1;

                        const left = (x1 / width) * 100;
                        const top = (y1 / height) * 100;
                        const styleW = (f_width / width) * 100;
                        const styleH = (f_height / height) * 100;

                        return (
                            <div
                                key={`fig-${idx}`}
                                className="absolute cursor-pointer pointer-events-auto border-2 border-transparent hover:border-indigo-500/40 hover:bg-indigo-500/5 transition-all rounded-lg group flex items-start justify-end p-2"
                                style={{
                                    left: `${left}%`,
                                    top: `${top}%`,
                                    width: `${styleW}%`,
                                    height: `${styleH}%`,
                                }}
                                onClick={(e) => {
                                    e.stopPropagation();
                                    if (onAskAI) {
                                        const type = fig.label === 'equation' ? '数式' : '図表';
                                        onAskAI(`${type}の解説をお願いします。`);
                                    }
                                }}
                                title={`${fig.label || 'figure'} click to explain`}
                            >
                                <div className="hidden group-hover:flex items-center gap-1.5 bg-indigo-600 text-white text-[10px] px-2.5 py-1.5 rounded-lg shadow-xl font-bold transform -translate-y-2 opacity-0 group-hover:opacity-100 group-hover:translate-y-0 transition-all duration-200">
                                    <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                    </svg>
                                    AIで解説
                                </div>
                            </div>
                        );
                    })}
                </div>

                {/* Selection Menu */}
                {selectionMenu && (
                    <div
                        className="absolute z-50 flex gap-1 bg-gray-900 text-white p-1.5 rounded-lg shadow-xl transform -translate-x-1/2 -translate-y-full"
                        style={{ left: `${selectionMenu.x}%`, top: `${selectionMenu.y}%`, marginTop: '-10px' }}
                        onMouseDown={(e) => e.stopPropagation()} // Prevent closing on click
                    >
                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                if (onWordClick) onWordClick(selectionMenu.text, selectionMenu.context, selectionMenu.coords);
                                setSelectionMenu(null);
                                setSelectionStart(null);
                                setSelectionEnd(null);
                            }}
                            className="px-3 py-1.5 hover:bg-gray-700 rounded text-xs font-bold flex items-center gap-1 transition-colors"
                        >
                            <span>文A</span> Translate
                        </button>
                        <div className="w-px bg-gray-700 mx-1"></div>
                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                if (onTextSelect) onTextSelect(selectionMenu.text, selectionMenu.coords);
                                setSelectionMenu(null);
                                setSelectionStart(null);
                                setSelectionEnd(null);
                            }}
                            className="px-3 py-1.5 hover:bg-gray-700 rounded text-xs font-bold flex items-center gap-1 transition-colors"
                        >
                            <span>📝</span> Note
                        </button>

                        {/* Triangle arrow */}
                        <div className="absolute left-1/2 bottom-0 w-2 h-2 bg-gray-900 transform -translate-x-1/2 translate-y-1/2 rotate-45"></div>
                    </div>
                )}

            </div>
        </div>
    );
};

export default PDFPage;

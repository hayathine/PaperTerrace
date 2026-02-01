import React, { useMemo } from 'react';
import { PageData } from './types';
import StampOverlay from '../Stamps/StampOverlay';
import BoxOverlay from './BoxOverlay';
import { Stamp } from '../Stamps/types';

const FIG_TYPE_LABEL: Record<string, string> = {
    'table': '表',
    'figure': '図',
    'equation': '数式',
    'image': '画像'
};

interface PDFPageProps {
    page: PageData;
    scale?: number;
    onWordClick?: (word: string, context?: string, coords?: { page: number, x: number, y: number }) => void;
    onTextSelect?: (text: string, coords: { page: number, x: number, y: number }) => void;
    onAskAI?: (prompt: string) => void;
    // Stamp props
    stamps?: Stamp[];
    isStampMode?: boolean;
    onAddStamp?: (page: number, x: number, y: number) => void;
    // Area selection props
    isAreaMode?: boolean;
    onAreaSelect?: (coords: { page: number, x: number, y: number, width: number, height: number }) => void;
    jumpTarget?: { page: number, x: number, y: number, term?: string } | null;
    evidenceHighlight?: { page: number, text: string } | null;
}

const WordBox = React.memo(({ 
    idx, w, width, height, isSelected, isJumpHighlight, isEvidenceHighlight, isStampMode, onMouseDown, onMouseEnter, onClick 
}: { 
    idx: number, w: any, width: number, height: number, isSelected: boolean, isJumpHighlight: boolean, 
    isEvidenceHighlight: boolean,
    isStampMode: boolean, onMouseDown: (idx: number) => void, onMouseEnter: (idx: number) => void, onClick: (idx: number, w: any) => void 
}) => {
    const [x1, y1, x2, y2] = w.bbox;
    const w_width = x2 - x1;
    const w_height = y2 - y1;

    const left = (x1 / width) * 100;
    const top = (y1 / height) * 100;
    const styleW = (w_width / width) * 100;
    const styleH = (w_height / height) * 100;

    return (
        <div
            className={`absolute rounded-sm group ${!isStampMode ? 'cursor-pointer' : 'pointer-events-none'} 
                ${!isStampMode && !isSelected && !isJumpHighlight && !isEvidenceHighlight ? 'hover:bg-yellow-300/30' : ''} 
                ${isSelected ? 'bg-indigo-500/30 border border-indigo-500/50' : ''}
                ${isEvidenceHighlight ? 'bg-emerald-400/40 border border-emerald-600/50 z-10 shadow-[0_0_8px_rgba(52,211,153,0.3)]' : ''}
                ${isJumpHighlight ? 'bg-yellow-400/60 border-2 border-yellow-600 shadow-[0_0_15px_rgba(250,204,21,0.5)] z-20 animate-bounce-subtle' : ''}`}
            style={{
                left: `${left}%`,
                top: `${top}%`,
                width: `${styleW}%`,
                height: `${styleH}%`,
                willChange: isSelected || isJumpHighlight ? 'transform, opacity' : 'auto'
            }}
            onMouseDown={(e) => {
                if (isStampMode) return;
                e.preventDefault();
                e.stopPropagation();
                onMouseDown(idx);
            }}
            onMouseEnter={() => onMouseEnter(idx)}
            onClick={(e) => {
                e.stopPropagation();
                onClick(idx, w);
            }}
            title={w.word}
        />
    );
});

const PDFPage: React.FC<PDFPageProps> = ({
    page,
    onWordClick,
    onTextSelect,
    onAskAI,
    stamps = [],
    isStampMode = false,
    onAddStamp,
    isAreaMode = false,
    onAreaSelect,
    jumpTarget,
    evidenceHighlight
}) => {
    const { width, height, words, figures, links, image_url, page_num } = page;

    // Evidence Highlight Logic using Phrase Match
    const evidenceIndices = React.useMemo(() => {
        if (!evidenceHighlight || evidenceHighlight.page !== page_num || !words || words.length === 0) return null;
        
        const fullText = words.map(w => w.word.toLowerCase()).join(' ');
        const snippet = evidenceHighlight.text.toLowerCase().trim();
        
        const index = fullText.indexOf(snippet);
        if (index === -1) return null;

        // Find which words fall into this range
        let currentPos = 0;
        const resultIndices: number[] = [];
        for (let i = 0; i < words.length; i++) {
            const word = words[i].word.toLowerCase();
            const wordEnd = currentPos + word.length;
            
            // Check if this word overlaps with the matched snippet range [index, index + snippet.length]
            if (wordEnd > index && currentPos < index + snippet.length) {
                resultIndices.push(i);
            }
            currentPos += word.length + 1; // +1 for the join(' ') space
        }
        return resultIndices;
    }, [evidenceHighlight, page_num, words]);

    const isWordInEvidence = React.useCallback((idx: number) => {
        return evidenceIndices?.includes(idx) || false;
    }, [evidenceIndices]);

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
            className="relative mb-8 shadow-2xl rounded-xl overflow-hidden bg-white border border-slate-200/50 mx-auto transform-gpu"
            style={{ 
                maxWidth: '100%',
                contentVisibility: 'auto',
                containIntrinsicSize: '1px 1100px', // Estimate for a typical A4-style page
                willChange: 'transform'
            }}
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
                    style={{ imageRendering: 'high-quality' as any }}
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
                        const isSelected = selectionStart !== null && selectionEnd !== null &&
                            ((idx >= selectionStart && idx <= selectionEnd) || (idx >= selectionEnd && idx <= selectionStart));

                        const isJumpHighlight = jumpTarget && jumpTarget.page === page_num && (
                            // Use a small epsilon for coordinate matching
                            Math.abs(((w.bbox[0] + w.bbox[2]) / 2 / width) - jumpTarget.x) < 0.005 && 
                            Math.abs(((w.bbox[1] + w.bbox[3]) / 2 / height) - jumpTarget.y) < 0.005
                        );

                        const isEvidenceHighlight = isWordInEvidence(idx);

                        return (
                            <WordBox
                                key={`${idx}`}
                                idx={idx}
                                w={w}
                                width={width}
                                height={height}
                                isSelected={isSelected}
                                isJumpHighlight={!!isJumpHighlight}
                                isEvidenceHighlight={isEvidenceHighlight}
                                isStampMode={isStampMode || isAreaMode}
                                onMouseDown={(i) => {
                                    if (isAreaMode) return;
                                    setIsDragging(true);
                                    setSelectionStart(i);
                                    setSelectionEnd(i);
                                    setSelectionMenu(null);
                                }}
                                onMouseEnter={(i) => {
                                    if (isDragging && selectionStart !== null) {
                                        setSelectionEnd(i);
                                    }
                                }}
                                onClick={(i, word) => {
                                    if (!isStampMode && !isAreaMode && onWordClick) {
                                        if (selectionStart === selectionEnd && !selectionMenu) {
                                            const cleanWord = word.word.replace(/^[.,;!?(){}[\]"']+|[.,;!?(){}[\]"']+$/g, '');
                                            const start = Math.max(0, i - 50);
                                            const end = Math.min(words.length, i + 50);
                                            const context = words.slice(start, end).map(w => w.word).join(' ');

                                            const wordCenterX = (word.bbox[0] + word.bbox[2]) / 2 / width;
                                            const wordCenterY = (word.bbox[1] + word.bbox[3]) / 2 / height;

                                            onWordClick(cleanWord, context, { page: page_num, x: wordCenterX, y: wordCenterY });
                                        }
                                    }
                                }}
                            />
                        );
                    })}
                </div>
                
                {/* Figure/Equation Overlays */}
                <div className="absolute inset-0 w-full h-full z-20 pointer-events-none">
                    {figures?.map((fig, idx) => {
                        const [x1, y1, x2, y2] = fig.bbox;
                        const f_width = x2 - x1;
                        const f_height = y2 - y1;

                        const left = (x1 / width) * 100;
                        const top = (y1 / height) * 100;
                        const styleW = (f_width / width) * 100;
                        const styleH = (f_height / height) * 100;

                        return (
                            <div
                                key={`fig-${idx}`}
                                className="absolute cursor-pointer pointer-events-auto border border-indigo-400/20 hover:border-indigo-500/60 hover:bg-indigo-500/5 transition-all rounded-xl group overflow-hidden"
                                style={{
                                    left: `${left}%`,
                                    top: `${top}%`,
                                    width: `${styleW}%`,
                                    height: `${styleH}%`,
                                }}
                                onClick={(e) => {
                                    e.stopPropagation();
                                    if (onAskAI) {
                                        const typeName = FIG_TYPE_LABEL[fig.label?.toLowerCase() || ''] || '図表';
                                        onAskAI(`${typeName}の解説をお願いします。`);
                                    }
                                }}
                                title={`${fig.label || 'figure'} click to explain`}
                            >
                                {/* Background Badge for Label */}
                                <div className="absolute top-2 left-2 px-2 py-0.5 bg-indigo-500/80 backdrop-blur-sm text-white text-[9px] font-black uppercase tracking-tighter rounded-md opacity-40 group-hover:opacity-100 transition-opacity">
                                    {fig.label || 'FIG'}
                                </div>

                                {/* Central Action Button */}
                                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 flex flex-col items-center gap-2">
                                    <div className="w-10 h-10 bg-white/20 group-hover:bg-indigo-600 backdrop-blur-md rounded-full flex items-center justify-center shadow-lg border border-white/30 group-hover:border-indigo-400 transition-all duration-300 transform group-hover:scale-110">
                                        <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                                        </svg>
                                    </div>
                                    <div className="opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                                        <span className="bg-slate-900/90 text-white text-[10px] px-3 py-1 rounded-full font-bold shadow-2xl backdrop-blur-sm whitespace-nowrap border border-white/10">
                                            AIで解説
                                        </span>
                                    </div>
                                </div>

                                {/* Pulse Effect for higher discoverability */}
                                <div className="absolute inset-0 bg-indigo-500/5 animate-pulse-slow pointer-events-none group-hover:hidden"></div>
                            </div>
                        );
                    })}
                </div>

                {/* Link Overlays */}
                <div className="absolute inset-0 w-full h-full z-20 pointer-events-none">
                    {links?.map((link, idx) => {
                        const [x1, y1, x2, y2] = link.bbox;
                        const l_width = x2 - x1;
                        const l_height = y2 - y1;
                        const left = (x1 / width) * 100;
                        const top = (y1 / height) * 100;
                        const styleW = (l_width / width) * 100;
                        const styleH = (l_height / height) * 100;

                        return (
                            <button
                                key={`link-${idx}`}
                                className="absolute cursor-pointer pointer-events-auto border border-blue-400/0 hover:border-blue-400/50 hover:bg-blue-400/10 transition-all rounded-sm z-30"
                                style={{
                                    left: `${left}%`,
                                    top: `${top}%`,
                                    width: `${styleW}%`,
                                    height: `${styleH}%`,
                                }}
                                onClick={(e) => {
                                    e.stopPropagation();
                                    window.open(link.url, '_blank', 'noopener,noreferrer');
                                }}
                                title={link.url}
                            />
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

export default React.memo(PDFPage);

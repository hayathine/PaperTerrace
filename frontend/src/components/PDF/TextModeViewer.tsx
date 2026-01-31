import React, { useRef } from 'react';
import { PageData } from './types';

interface TextModeViewerProps {
    pages: PageData[];
    onWordClick?: (word: string, context?: string, coords?: { page: number, x: number, y: number }) => void;
    onTextSelect?: (text: string, coords: { page: number, x: number, y: number }) => void;
    jumpTarget?: { page: number, x: number, y: number, term?: string } | null;
    onStackPaper?: (url: string, title?: string) => void;
}

const TextModeViewer: React.FC<TextModeViewerProps> = ({ pages, onWordClick, onTextSelect, jumpTarget, onStackPaper }) => {
    
    const [selectionMenu, setSelectionMenu] = React.useState<{ x: number, y: number, text: string, coords: any } | null>(null);

    const handleMouseUp = (e: React.MouseEvent, page: PageData) => {
        const selection = window.getSelection();
        const selectionText = selection?.toString().trim();
        
        if (selection && selectionText && selectionText.length > 0) {
            // Get selection coordinates relative to the page container
            const rect = e.currentTarget.getBoundingClientRect();
            
            // Selection bounding box for precise menu positioning
            const range = selection.getRangeAt(0);
            const rangeRect = range.getBoundingClientRect();
            
            // Position menu above the center of the selection
            const menuX = ((rangeRect.left + rangeRect.right) / 2 - rect.left) / rect.width * 100;
            const menuY = (rangeRect.top - rect.top) / rect.height * 100;

            const centerX = ((rangeRect.left + rangeRect.right) / 2 - rect.left) / rect.width;
            const centerY = ((rangeRect.top + rangeRect.bottom) / 2 - rect.top) / rect.height;

            setSelectionMenu({
                x: menuX,
                y: menuY,
                text: selectionText,
                coords: { page: page.page_num, x: centerX, y: centerY }
            });
        } else {
            // If it's a simple click (no text selected), hide the menu
            setSelectionMenu(null);
        }
    };

    React.useEffect(() => {
        const handleClickOutside = (e: MouseEvent) => {
            // Don't close if clicking inside the menu
            if ((e.target as HTMLElement).closest('.selection-menu')) return;
            setSelectionMenu(null);
        };
        if (selectionMenu) document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, [selectionMenu]);

    if (!pages || pages.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center p-12 text-slate-400">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500 mb-4"></div>
                <p>読み込み中...</p>
            </div>
        );
    }

    return (
        <div className="w-full max-w-5xl mx-auto p-4 space-y-12 pb-32">
            <div className="sticky top-0 z-40 bg-white/90 backdrop-blur-md px-4 py-3 rounded-2xl shadow-sm border border-slate-100 flex items-center justify-between mb-8">
                <div className="flex items-center gap-2">
                    <span className="bg-indigo-100 text-indigo-700 px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider">
                        Native Selection Mode (Beta)
                    </span>
                    <p className="text-xs text-slate-500 hidden sm:block">テキストを自由に選択して、翻訳やスタックへの追加が可能です。</p>
                </div>
            </div>

            {pages.map((page) => (
                <div 
                    key={page.page_num}
                    id={`text-page-${page.page_num}`}
                    className="relative shadow-2xl rounded-2xl overflow-hidden bg-white border border-slate-200 group mx-auto"
                    style={{ maxWidth: '100%', userSelect: 'none' }} 
                    onMouseUp={(e) => handleMouseUp(e, page)}
                >
                    {/* Header */}
                    <div className="bg-slate-50 border-b border-slate-100 px-6 py-2 flex justify-between items-center select-none">
                        <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">
                            Page {page.page_num}
                        </span>
                    </div>

                    {/* Content Container */}
                    <div className="relative w-full overflow-hidden">
                        {/* PDF Image (Base Layer) */}
                        <img 
                            src={page.image_url} 
                            alt={`Page ${page.page_num}`} 
                            className="w-full h-auto block select-none pointer-events-none"
                            loading="lazy"
                        />

                        {/* Transparent Text Layer (Overlay Layer) */}
                        <div className="absolute inset-0 z-10 w-full h-full cursor-text selection:bg-indigo-500/40" style={{ userSelect: 'text' }}>
                            {page.words.map((w, idx) => {
                                const [x1, y1, x2, y2] = w.bbox;
                                const left = (x1 / page.width) * 100;
                                const top = (y1 / page.height) * 100;
                                const styleW = ((x2 - x1) / page.width) * 100;
                                const styleH = ((y2 - y1) / page.height) * 100;

                                // Check for jump highlight
                                const isJumpHighlight = jumpTarget && 
                                    jumpTarget.page === page.page_num && 
                                    jumpTarget.term && 
                                    w.word.toLowerCase().includes(jumpTarget.term.toLowerCase());

                                return (
                                    <span 
                                        key={idx}
                                        className={`absolute text-transparent overflow-hidden whitespace-pre transition-all
                                            ${isJumpHighlight ? 'bg-yellow-400/40 border-b-2 border-yellow-600' : ''}`}
                                        style={{
                                            left: `${left}%`,
                                            top: `${top}%`,
                                            width: `${styleW}%`,
                                            height: `${styleH}%`,
                                            // Scale font size based on bbox height. 
                                            // Using 70% of the styleH as a safe bet for browser selection boxes.
                                            fontSize: `${styleH * 0.8}cqw`, // Typos: cqw actually depends on container. 
                                            // Let's use a simpler approach: very large line-height to fill the box
                                            lineHeight: 1,
                                            pointerEvents: 'auto'
                                        }}
                                    >
                                        {/* IMPORTANT: Add space for natural selection/copying */}
                                        {w.word}{' '}
                                    </span>
                                );
                            })}
                        </div>
                    </div>

                    {/* Selection Menu */}
                    {selectionMenu && (
                        <div
                            className="selection-menu absolute z-50 flex gap-1 bg-slate-900 text-white p-1.5 rounded-xl shadow-2xl transform -translate-x-1/2 -translate-y-full"
                            style={{ 
                                left: `${selectionMenu.x}%`, 
                                top: `${selectionMenu.y}%`, 
                                marginTop: '-12px' 
                            }}
                            onMouseDown={(e) => e.stopPropagation()}
                        >
                            <button
                                onClick={(e) => {
                                    e.stopPropagation();
                                    if (onWordClick) onWordClick(selectionMenu.text, undefined, selectionMenu.coords);
                                    setSelectionMenu(null);
                                }}
                                className="px-3 py-1.5 hover:bg-slate-700 rounded-lg text-xs font-bold flex items-center gap-1 transition-colors"
                            >
                                <span>文A</span> Translate
                            </button>
                            <div className="w-px bg-slate-700 mx-1"></div>
                            <button
                                onClick={(e) => {
                                    e.stopPropagation();
                                    if (onTextSelect) onTextSelect(selectionMenu.text, selectionMenu.coords);
                                    setSelectionMenu(null);
                                }}
                                className="px-3 py-1.5 hover:bg-slate-700 rounded-lg text-xs font-bold flex items-center gap-1 transition-colors"
                            >
                                <span>📝</span> Note
                            </button>
                            <div className="w-px bg-slate-700 mx-1"></div>
                            <button
                                onClick={(e) => {
                                    e.stopPropagation();
                                    if (onStackPaper) onStackPaper(selectionMenu.text);
                                    setSelectionMenu(null);
                                }}
                                className="px-3 py-1.5 hover:bg-slate-700 rounded-lg text-xs font-bold flex items-center gap-1 transition-colors"
                            >
                                <span>📚</span> Stack
                            </button>
                            {/* Triangle arrow */}
                            <div className="absolute left-1/2 bottom-0 w-2 h-2 bg-slate-900 transform -translate-x-1/2 translate-y-1/2 rotate-45"></div>
                        </div>
                    )}
                </div>
            ))}
        </div>
    );
};

export default TextModeViewer;

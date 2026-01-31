import React from 'react';
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

    // Group words into lines for better selection behavior
    const pagesWithLines = React.useMemo(() => {
        return pages.map(page => {
            const lines: { words: typeof page.words, bbox: number[] }[] = [];
            // Sort words primarily by top position, secondarily by left
            const sortedWords = [...page.words].sort((a, b) => (a.bbox[1] - b.bbox[1]) || (a.bbox[0] - b.bbox[0]));
            
            sortedWords.forEach(word => {
                const wordY1 = word.bbox[1];
                const wordHeight = word.bbox[3] - word.bbox[1];
                
                // Find a line that this word might belong to (similar Y coordinate)
                const line = lines.find(l => Math.abs(wordY1 - l.bbox[1]) < wordHeight * 0.5);
                
                if (line) {
                    line.words.push(word);
                    line.bbox[0] = Math.min(line.bbox[0], word.bbox[0]);
                    line.bbox[1] = Math.min(line.bbox[1], word.bbox[1]);
                    line.bbox[2] = Math.max(line.bbox[2], word.bbox[2]);
                    line.bbox[3] = Math.max(line.bbox[3], word.bbox[3]);
                } else {
                    lines.push({
                        words: [word],
                        bbox: [...word.bbox]
                    });
                }
            });

            // Sort words within each line by X coordinate
            lines.forEach(line => line.words.sort((a, b) => a.bbox[0] - b.bbox[0]));
            return { ...page, lines };
        });
    }, [pages]);

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

            {pagesWithLines.map((page) => (
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
                            {page.lines.map((line, lIdx) => {
                                const [lx1, ly1, lx2, ly2] = line.bbox;
                                const lTop = (ly1 / page.height) * 100;
                                const lLeft = (lx1 / page.width) * 100;
                                const lWidth = ((lx2 - lx1) / page.width) * 100;
                                const lHeight = ((ly2 - ly1) / page.height) * 100;

                                return (
                                    <div
                                        key={lIdx}
                                        className="absolute text-transparent whitespace-pre flex items-center"
                                        style={{
                                            top: `${lTop}%`,
                                            left: `${lLeft}%`,
                                            width: `${lWidth}%`,
                                            height: `${lHeight}%`,
                                            // Font size scales with line height
                                            fontSize: `${lHeight * 0.8}cqw`, 
                                            // Avoid gaps between words in selection
                                            letterSpacing: '-0.05em'
                                        }}
                                    >
                                        {line.words.map((w, wIdx) => {
                                            // Check for jump highlight
                                            const isJumpHighlight = jumpTarget && 
                                                jumpTarget.page === page.page_num && 
                                                jumpTarget.term && 
                                                w.word.toLowerCase().includes(jumpTarget.term.toLowerCase());

                                            return (
                                                <span 
                                                    key={wIdx}
                                                    className={`transition-all ${isJumpHighlight ? 'bg-yellow-400/40 border-b-2 border-yellow-600' : ''}`}
                                                    style={{ pointerEvents: 'auto' }}
                                                >
                                                    {w.word}{' '}
                                                </span>
                                            );
                                        })}
                                    </div>
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

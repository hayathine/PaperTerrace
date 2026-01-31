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

    // Group words into lines, aware of multi-column layouts
    const pagesWithLines = React.useMemo(() => {
        return pages.map(page => {
            const words = [...page.words];
            if (words.length === 0) return { ...page, lines: [] };

            // 1. Detect Columns (Simple heuristic: find if there's a large gap in X coordinates)
            // Sort by X to find horizontal distribution
            const sortedByX = [...words].sort((a, b) => a.bbox[0] - b.bbox[0]);
            const columns: (typeof words)[] = [];
            let currentColumn: typeof words = [];

            // A gap of more than 10% of page width often indicates a new column
            const columnGapThreshold = page.width * 0.1;

            sortedByX.forEach((word, i) => {
                if (i > 0 && word.bbox[0] - sortedByX[i-1].bbox[2] > columnGapThreshold) {
                    columns.push(currentColumn);
                    currentColumn = [word];
                } else {
                    currentColumn.push(word);
                }
            });
            columns.push(currentColumn);

            // 2. For each column, group words into lines
            const allLines: { words: typeof page.words, bbox: number[] }[] = [];

            columns.forEach(colWords => {
                // Sort by Y for line grouping within this column
                const sortedByY = colWords.sort((a, b) => (a.bbox[1] - b.bbox[1]) || (a.bbox[0] - b.bbox[0]));
                const colLines: { words: typeof page.words, bbox: number[] }[] = [];

                sortedByY.forEach(word => {
                    const wordY1 = word.bbox[1];
                    const wordHeight = word.bbox[3] - word.bbox[1];
                    
                    // Find if word belongs to an existing line in this column
                    const line = colLines.find(l => Math.abs(wordY1 - l.bbox[1]) < wordHeight * 0.4);
                    
                    if (line) {
                        line.words.push(word);
                        line.bbox[0] = Math.min(line.bbox[0], word.bbox[0]);
                        line.bbox[1] = Math.min(line.bbox[1], word.bbox[1]);
                        line.bbox[2] = Math.max(line.bbox[2], word.bbox[2]);
                        line.bbox[3] = Math.max(line.bbox[3], word.bbox[3]);
                    } else {
                        colLines.push({ words: [word], bbox: [...word.bbox] });
                    }
                });

                // Sort words within each line by X
                colLines.forEach(line => line.words.sort((a, b) => a.bbox[0] - b.bbox[0]));
                allLines.push(...colLines);
            });

            return { ...page, lines: allLines };
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
                    className="relative shadow-sm bg-white border border-slate-200 group mx-auto"
                    style={{ maxWidth: '100%', userSelect: 'none' }} 
                    onMouseUp={(e) => handleMouseUp(e, page)}
                >
                    {/* Header */}
                    <div className="bg-slate-50 border-b border-slate-200 px-4 py-1.5 flex justify-between items-center select-none">
                        <span className="text-[9px] font-black text-slate-400 uppercase tracking-[0.2em]">
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
                        <div className="absolute inset-0 z-10 w-full h-full cursor-text selection:bg-indigo-600/30" style={{ userSelect: 'text' }}>
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
                                            fontSize: `${lHeight * 0.8}cqw`, 
                                            letterSpacing: '-0.05em'
                                        }}
                                    >
                                        {line.words.map((w, wIdx) => {
                                            const isJumpHighlight = jumpTarget && 
                                                jumpTarget.page === page.page_num && 
                                                jumpTarget.term && 
                                                w.word.toLowerCase().includes(jumpTarget.term.toLowerCase());

                                            return (
                                                <span 
                                                    key={wIdx}
                                                    className={`transition-all ${isJumpHighlight ? 'bg-yellow-400/40 border-b border-yellow-600' : ''}`}
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
                            className="selection-menu absolute z-50 flex gap-0 bg-slate-900 text-white rounded shadow-lg overflow-hidden transform -translate-x-1/2 -translate-y-full border border-slate-800"
                            style={{ 
                                left: `${selectionMenu.x}%`, 
                                top: `${selectionMenu.y}%`, 
                                marginTop: '-10px' 
                            }}
                            onMouseDown={(e) => e.stopPropagation()}
                        >
                            <button
                                onClick={(e) => {
                                    e.stopPropagation();
                                    if (onWordClick) onWordClick(selectionMenu.text, undefined, selectionMenu.coords);
                                    setSelectionMenu(null);
                                }}
                                className="px-3 py-1.5 hover:bg-indigo-600 text-[10px] font-bold uppercase tracking-wider flex items-center gap-1.5 transition-colors border-r border-slate-800"
                            >
                                <span>文A</span> Translate
                            </button>
                            <button
                                onClick={(e) => {
                                    e.stopPropagation();
                                    if (onTextSelect) onTextSelect(selectionMenu.text, selectionMenu.coords);
                                    setSelectionMenu(null);
                                }}
                                className="px-3 py-1.5 hover:bg-indigo-600 text-[10px] font-bold uppercase tracking-wider flex items-center gap-1.5 transition-colors border-r border-slate-800"
                            >
                                <span>📝</span> Note
                            </button>
                            <button
                                onClick={(e) => {
                                    e.stopPropagation();
                                    if (onStackPaper) onStackPaper(selectionMenu.text);
                                    setSelectionMenu(null);
                                }}
                                className="px-3 py-1.5 hover:bg-indigo-600 text-[10px] font-bold uppercase tracking-wider flex items-center gap-1.5 transition-colors"
                            >
                                <span>📚</span> Stack
                            </button>
                        </div>
                    )}
                </div>
            ))}
        </div>
    );
};

export default TextModeViewer;

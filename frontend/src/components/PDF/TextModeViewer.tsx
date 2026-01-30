import React from 'react';
import { PageData } from './types';

interface TextModeViewerProps {
    pages: PageData[];
    onWordClick?: (word: string, context?: string, coords?: { page: number, x: number, y: number }) => void;
    onTextSelect?: (text: string, coords: { page: number, x: number, y: number }) => void;
}

const TextModeViewer: React.FC<TextModeViewerProps> = ({ pages, onWordClick, onTextSelect }) => {
    
    const handleWordClick = (word: string, pageData: PageData, bbox: number[], context?: string) => {
        if (onWordClick) {
            // Calculate coords
            // bbox is [x1, y1, x2, y2]
            // We need % relative coords 0-1
            const [x1, y1, x2, y2] = bbox;
            const x = ((x1 + x2) / 2) / pageData.width;
            const y = ((y1 + y2) / 2) / pageData.height;

            const cleanWord = word.replace(/^[.,;!?(){}[\]"']+|[.,;!?(){}[\]"']+$/g, '');
            if (!cleanWord) return;

            onWordClick(cleanWord, context, { page: pageData.page_num, x, y });
        }
    };

    const handleMouseUp = (pageData: PageData) => {
        const selection = window.getSelection();
        if (selection && selection.toString().trim().length > 0 && onTextSelect) {
            const text = selection.toString().trim();
            // We can't easily get precise coords from text selection in plain text mode
            // Default to top of page or center?
            // Let's use page center as fallback
            onTextSelect(text, { page: pageData.page_num, x: 0.5, y: 0.5 });
        }
    };

    if (!pages || pages.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center p-12 text-slate-400">
                <p>Waiting for pages...</p>
            </div>
        );
    }

    return (
        <div className="space-y-6 animate-fade-in w-full max-w-5xl mx-auto">
            {pages.map((page) => (
                <div 
                    key={page.page_num}
                    id={`text-page-${page.page_num}`}
                    className="relative shadow-xl rounded-xl overflow-hidden bg-white border border-slate-200/50"
                    onMouseUp={() => handleMouseUp(page)}
                >
                    {/* Header / Page Number */}
                    <div className="bg-gray-50 border-b border-gray-100 px-4 py-2 flex justify-between items-center">
                        <span className="text-xs font-bold text-gray-400 uppercase tracking-widest">
                            Page {page.page_num}
                        </span>
                        <div className="flex gap-2">
                             <button
                                onClick={() => {
                                    const text = page.words.map(w => w.word).join(' ');
                                    navigator.clipboard.writeText(text);
                                }}
                                className="text-slate-400 hover:text-indigo-600 transition-colors p-1 rounded-md hover:bg-indigo-50"
                                title="Copy page text"
                            >
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3" />
                                </svg>
                            </button>
                        </div>
                    </div>

                    {/* Content Area */}
                    <div className="p-8 md:p-12">
                        <article className="prose prose-slate prose-lg max-w-none font-serif leading-relaxed text-slate-800 break-words">
                            <p>
                                {page.words.map((w, i) => (
                                    <span 
                                        key={i}
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            // Extract context (surrounding words)
                                            const start = Math.max(0, i - 15);
                                            const end = Math.min(page.words.length, i + 15);
                                            const context = page.words.slice(start, end).map(wd => wd.word).join(' ');
                                            
                                            handleWordClick(w.word, page, w.bbox, context);
                                        }}
                                        className="hover:bg-yellow-200 cursor-pointer rounded-sm px-0.5 transition-colors inline-block"
                                    >
                                        {w.word}{' '}
                                    </span>
                                ))}
                            </p>
                        </article>
                    </div>
                </div>
            ))}
        </div>
    );
};

export default TextModeViewer;

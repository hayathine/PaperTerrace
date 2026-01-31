import React from 'react';
import { PageData } from './types';

interface TextModeViewerProps {
    pages: PageData[];
    onWordClick?: (word: string, context?: string, coords?: { page: number, x: number, y: number }) => void;
    onTextSelect?: (text: string, coords: { page: number, x: number, y: number }) => void;
    jumpTarget?: { page: number, x: number, y: number, term?: string } | null;
}

const TextModeViewer: React.FC<TextModeViewerProps> = ({ pages, onWordClick, onTextSelect, jumpTarget }) => {
    
    const handleWordClick = (word: string, pageData: PageData, bbox: number[], context?: string) => {
        if (onWordClick) {
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
        <div className="space-y-12 animate-fade-in w-full max-w-7xl mx-auto px-4 pb-32">
            {/* Header / Mode Indicator */}
            <div className="flex items-center justify-between bg-white/50 backdrop-blur p-4 rounded-2xl border border-slate-200 shadow-sm">
                <div className="flex items-center gap-4">
                    <div className="w-10 h-10 bg-indigo-600 rounded-xl flex items-center justify-center text-white shadow-lg shadow-indigo-200">
                        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                    </div>
                    <div>
                        <h2 className="text-lg font-bold text-slate-800 tracking-tight">Reading Mode: Text & Image</h2>
                        <p className="text-xs text-slate-500 font-medium">Comparing extracted text with original document.</p>
                    </div>
                </div>
            </div>

            {pages.map((page) => (
                <div 
                    key={page.page_num}
                    id={`text-page-${page.page_num}`}
                    className="relative bg-white rounded-3xl border border-slate-200 shadow-xl overflow-hidden scroll-mt-20"
                    onMouseUp={() => handleMouseUp(page)}
                >
                    {/* Page Bar */}
                    <div className="px-6 py-4 bg-slate-50 border-b border-slate-100 flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <span className="px-3 py-1 bg-white rounded-full border border-slate-200 text-[10px] font-black text-indigo-600 shadow-sm">
                                PAGE {page.page_num}
                            </span>
                        </div>
                        <button
                            onClick={() => {
                                const text = page.words.length > 0 
                                    ? page.words.map(w => w.word).join(' ') 
                                    : (page.content || '');
                                navigator.clipboard.writeText(text);
                            }}
                            className="p-2 hover:bg-white rounded-xl transition-all text-slate-400 hover:text-indigo-600 border border-transparent hover:border-slate-100 shadow-none hover:shadow-sm"
                            title="Copy text"
                        >
                            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3" />
                            </svg>
                        </button>
                    </div>

                    {/* Split View */}
                    <div className="grid grid-cols-1 lg:grid-cols-2">
                        {/* Image Panel */}
                        <div className="p-8 bg-slate-50/50 border-r border-slate-100 flex items-start justify-center group overflow-hidden">
                            <div className="relative group-hover:scale-[1.03] transition-transform duration-700 ease-out">
                                <img 
                                    src={page.image_url} 
                                    alt={`Original p.${page.page_num}`}
                                    className="max-w-full h-auto rounded-lg shadow-2xl border border-white"
                                />
                                <div className="absolute inset-0 bg-indigo-600/5 opacity-0 group-hover:opacity-100 transition-opacity rounded-lg pointer-events-none"></div>
                            </div>
                        </div>

                        {/* Text Panel */}
                        <div className="p-10 md:p-14 bg-white flex flex-col">
                            <article className="prose prose-slate prose-lg max-w-none font-serif leading-relaxed text-slate-800 flex-1">
                                {page.words.length > 0 ? (
                                    <div className="relative">
                                        {page.words.map((w, i) => {
                                            const [x1, y1, x2, y2] = w.bbox;
                                            const centerX = ((x1 + x2) / 2) / page.width;
                                            const centerY = ((y1 + y2) / 2) / page.height;
                                            const isJumpHighlight = jumpTarget && jumpTarget.page === page.page_num && (
                                                Math.abs(centerX - jumpTarget.x) < 0.015 && 
                                                Math.abs(centerY - jumpTarget.y) < 0.015
                                            );

                                            return (
                                                <span 
                                                    key={i}
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        const start = Math.max(0, i - 20);
                                                        const end = Math.min(page.words.length, i + 20);
                                                        const context = page.words.slice(start, end).map(wd => wd.word).join(' ');
                                                        handleWordClick(w.word, page, w.bbox, context);
                                                    }}
                                                    className={`inline-block mr-1 rounded-sm px-0.5 transition-all
                                                        ${isJumpHighlight 
                                                            ? 'bg-yellow-400 font-bold shadow-[0_0_15px_rgba(250,204,21,0.6)] scale-110 ring-4 ring-yellow-400/30 z-10' 
                                                            : 'hover:bg-indigo-100 cursor-pointer text-slate-700 hover:text-indigo-900'}`}
                                                >
                                                    {w.word}
                                                </span>
                                            );
                                        })}
                                    </div>
                                ) : (
                                    <div className="whitespace-pre-wrap text-slate-500 leading-relaxed font-sans text-base animate-pulse">
                                        {page.content || "Processing text recognition..."}
                                    </div>
                                )}
                            </article>
                            
                            {page.words.length === 0 && page.content && (
                                <div className="mt-12 p-5 bg-blue-50/50 rounded-2xl border border-blue-100 flex items-start gap-4">
                                    <div className="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center text-blue-600 shrink-0">
                                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                        </svg>
                                    </div>
                                    <div>
                                        <p className="text-[12px] text-blue-900 font-bold mb-1">Optical Character Recognition (OCR)</p>
                                        <p className="text-[11px] text-blue-800/70 leading-relaxed">
                                            Interactivity is limited on this page as it was processed via raw OCR. You can still select and copy text.
                                        </p>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            ))}
        </div>
    );
};

export default TextModeViewer;

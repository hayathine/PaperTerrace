import React, { useState, useEffect, useRef } from 'react';
import { PageData } from './types';
import PDFPage from './PDFPage';
import StampPalette from '../Stamps/StampPalette';
import { Stamp, StampType } from '../Stamps/types';
import { useAuth } from '../../contexts/AuthContext';
import TextModeViewer from './TextModeViewer';

interface PDFViewerProps {
    taskId?: string;
    initialData?: PageData[];
    uploadFile?: File | null;
    sessionId?: string;
    onWordClick?: (word: string, context?: string, coords?: { page: number, x: number, y: number }) => void;
    onTextSelect?: (text: string, coords: { page: number, x: number, y: number }) => void;
    onAreaSelect?: (imageUrl: string, coords: { page: number, x: number, y: number }) => void; // New prop
    jumpTarget?: { page: number, x: number, y: number, term?: string } | null;
    onStatusChange?: (status: 'idle' | 'uploading' | 'processing' | 'done' | 'error') => void;
    onPaperLoaded?: (paperId: string | null) => void;
    onAskAI?: (prompt: string) => void;
    onStackPaper?: (url: string, title?: string) => void;
}

const PDFViewer: React.FC<PDFViewerProps> = ({ uploadFile, onWordClick, onTextSelect, onAreaSelect, sessionId, jumpTarget, onStatusChange, onPaperLoaded, onAskAI, onStackPaper }) => {
    const { token } = useAuth();
    const [pages, setPages] = useState<PageData[]>([]);
    const [status, setStatus] = useState<'idle' | 'uploading' | 'processing' | 'done' | 'error'>('idle');
    const [errorMsg, setErrorMsg] = useState<string>('');
    const eventSourceRef = useRef<EventSource | null>(null);
    const [paperId, setPaperId] = useState<string | null>(null);
    // const containerRef = useRef<HTMLDivElement>(null); // Unused now

    // const containerRef = useRef<HTMLDivElement>(null); // Unused now


    // Stamp State
    // Modes: 'plaintext' (default), 'text', 'stamp', 'area'
    const [mode, setMode] = useState<'text' | 'stamp' | 'area' | 'plaintext'>('plaintext');
    const [stamps, setStamps] = useState<Stamp[]>([]);
    const [selectedStamp, setSelectedStamp] = useState<StampType>('👍');

    useEffect(() => {
        if (onStatusChange) {
            onStatusChange(status);
        }
    }, [status, onStatusChange]);

    useEffect(() => {
        if (uploadFile) {
            startAnalysis(uploadFile);
        }
        return () => {
            if (eventSourceRef.current) {
                eventSourceRef.current.close();
            }
        };
    }, [uploadFile]);

    // Fetch stamps when paperId is available
    useEffect(() => {
        if (paperId) {
            fetchStamps(paperId);
        }
        if (onPaperLoaded) {
            onPaperLoaded(paperId);
        }
    }, [paperId]);



    const fetchStamps = async (id: string) => {
        try {
            const headers: HeadersInit = {};
            if (token) headers['Authorization'] = `Bearer ${token}`;

            const res = await fetch(`/stamps/paper/${id}`, { headers });
            if (res.ok) {
                const data = await res.json();
                setStamps(data.stamps);
            }
        } catch (e) {
            console.error('Failed to fetch stamps', e);
        }
    };
    


    // Scroll to jump target when it changes
    useEffect(() => {
        if (jumpTarget) {
            const pageEl = document.getElementById(`page-${jumpTarget.page}`);
            if (pageEl) {
                // Find scrollable container (assuming one of the parents is overflow-y-auto)
                // In App.tsx it's the div with ".overflow-y-auto"
                const scroller = pageEl.closest('.overflow-y-auto');

                if (scroller) {
                    const pageRect = pageEl.getBoundingClientRect();
                    const scrollerRect = scroller.getBoundingClientRect();

                    // Current scroll position
                    const currentScrollTop = scroller.scrollTop;

                    // pageRect.top is relative to viewport
                    // We need offset from scroller top
                    // scrollerRect.top is viewport top of scroller

                    // Page top position inside the scrollable content
                    const pageTopInScroller = currentScrollTop + (pageRect.top - scrollerRect.top);

                    // Target Y within the page (height * percentage)
                    const targetYInPage = pageRect.height * (jumpTarget.y || 0); // Default to top if y is missing

                    // Center the target in the viewport (scroller height / 2)
                    const targetScrollTop = pageTopInScroller + targetYInPage - (scrollerRect.height / 2);

                    scroller.scrollTo({
                        top: targetScrollTop,
                        behavior: 'smooth'
                    });

                    // Also highlight the target location temporarily?
                } else {
                    // Fallback if no specific scroller found (e.g. window scroll)
                    pageEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
            }
        }
    }, [jumpTarget]);

    const startAnalysis = async (file: File) => {
        setStatus('uploading');
        setPages([]);
        setPaperId(null);
        setStamps([]);

        const formData = new FormData();
        formData.append('file', file);
        formData.append('lang', 'ja');
        formData.append('mode', 'json');
        if (sessionId) {
            formData.append('session_id', sessionId);
        }

        try {
            const headers: HeadersInit = {};
            if (token) headers['Authorization'] = `Bearer ${token}`;

            const response = await fetch('/analyze-pdf-json', {
                method: 'POST',
                headers, // FormData sets Content-Type boundary automatically, but we add Auth
                body: formData,
            });

            if (!response.ok) throw new Error('Upload failed');

            const data = await response.json();
            const { stream_url } = data;

            setStatus('processing');
            const es = new EventSource(stream_url);
            eventSourceRef.current = es;

            es.onmessage = (event) => {
                try {
                    const eventData = JSON.parse(event.data);
                    console.debug('[PDFViewer] SSE Message:', eventData.type, eventData);

                    if (eventData.type === 'page') {
                        setPages(prev => {
                            const newData = eventData.data;
                            const index = prev.findIndex(p => p.page_num === newData.page_num);
                            if (index !== -1) {
                                // Replace existing page data (update)
                                const newPages = [...prev];
                                newPages[index] = newData;
                                return newPages;
                            }
                            // Append new page
                            return [...prev, newData];
                        });
                    } else if (eventData.type === 'done') {
                        setStatus('done');
                        if (eventData.paper_id) {
                            setPaperId(eventData.paper_id);
                        }
                        es.close();
                    } else if (eventData.type === 'error') {
                        setStatus('error');
                        setErrorMsg(eventData.message);
                        es.close();
                    }
                } catch (e) {
                    // Ignore
                }
            };

            es.onerror = (err) => {
                console.error('SSE Error', err);
                es.close();
            };

        } catch (err: any) {
            setStatus('error');
            setErrorMsg(err.message);
        }
    };

    const handleWordClick = (word: string, context?: string, coords?: { page: number, x: number, y: number }) => {
        if (onWordClick) {
            onWordClick(word, context, coords);
        }
    };

    const handleTextSelect = (text: string, coords: { page: number, x: number, y: number }) => {
        if (onTextSelect) {
            onTextSelect(text, coords);
        }
    };

    const handleAreaSelect = async (coords: { page: number, x: number, y: number, width: number, height: number }) => {
        // Find page data
        const page = pages.find(p => p.page_num === coords.page);
        if (!page || !onAreaSelect) return;

        try {
            // Load image for cropping
            const img = new Image();
            img.crossOrigin = "anonymous";
            img.src = page.image_url;
            await new Promise((resolve) => img.onload = resolve);

            const canvas = document.createElement('canvas');
            // Coords are in relative [0-1] format
            const cropX = coords.x * img.naturalWidth;
            const cropY = coords.y * img.naturalHeight;
            const cropW = coords.width * img.naturalWidth;
            const cropH = coords.height * img.naturalHeight;

            canvas.width = cropW;
            canvas.height = cropH;

            const ctx = canvas.getContext('2d');
            if (!ctx) return;

            ctx.drawImage(img, cropX, cropY, cropW, cropH, 0, 0, cropW, cropH);

            // Upload the cropped image
            canvas.toBlob(async (blob) => {
                if (!blob) return;
                const formData = new FormData();
                formData.append('file', blob, 'crop.png');

                // We need token if auth is enabled
                const headers: HeadersInit = {};
                if (token) headers['Authorization'] = `Bearer ${token}`;

                const res = await fetch('/upload/image', {
                    method: 'POST',
                    headers,
                    body: formData
                });

                if (res.ok) {
                    const data = await res.json();
                    onAreaSelect(data.url, { page: coords.page, x: coords.x, y: coords.y });
                    // Switch back to text mode after selection?
                    setMode('text');
                }
            }, 'image/png');

        } catch (e) {
            console.error('Failed to crop/upload image', e);
        }
    };

    const handleAddStamp = async (page: number, x: number, y: number) => {
        if (!paperId) {
            alert('Paper ID not found. Please wait for analysis to complete.');
            return;
        }

        const newStamp: Stamp = {
            id: 'temp-' + Date.now(),
            type: selectedStamp,
            x,
            y,
            page_number: page,
        };

        // Optimistic update
        setStamps(prev => [...prev, newStamp]);

        try {
            const headers: HeadersInit = { 'Content-Type': 'application/json' };
            if (token) headers['Authorization'] = `Bearer ${token}`;

            const res = await fetch(`/stamps/paper/${paperId}`, {
                method: 'POST',
                headers,
                body: JSON.stringify({
                    stamp_type: selectedStamp,
                    x,
                    y,
                    page_number: page
                })
            });

            if (res.ok) {
                const data = await res.json();
                // Update ID from backend
                setStamps(prev => prev.map(s => s.id === newStamp.id ? { ...s, id: data.stamp_id } : s));
            } else {
                console.error('Failed to save stamp');
                // Rollback?
                setStamps(prev => prev.filter(s => s.id !== newStamp.id));
            }

        } catch (e) {
            console.error('Error saving stamp', e);
            setStamps(prev => prev.filter(s => s.id !== newStamp.id));
        }
    };

    return (
        <div className="w-full max-w-5xl mx-auto p-2 md:p-4 relative min-h-full pb-20">
            {status === 'idle' && !uploadFile && (
                <div className="text-center p-10 text-gray-400 border-2 border-dashed border-gray-200 rounded-xl">
                    Waiting for PDF...
                </div>
            )}

            {status === 'uploading' && (
                <div className="flex justify-center p-10">
                    <span className="animate-pulse text-blue-500">Uploading PDF...</span>
                </div>
            )}

            {status === 'error' && (
                <div className="bg-red-50 text-red-600 p-4 rounded-lg mb-4">
                    Error: {errorMsg}
                </div>
            )}

            {/* Toolbar */}
            {pages.length > 0 && (
                <div className="sticky top-4 z-40 flex justify-center mb-8">
                    <div className="bg-white/80 backdrop-blur-md p-1.5 rounded-2xl shadow-lg border border-slate-200/50 flex items-center gap-1">
                        <button
                            onClick={() => setMode('text')}
                            className={`px-4 py-2 rounded-xl flex items-center gap-2 text-xs font-bold transition-all duration-200 ${
                                mode === 'text' 
                                ? 'bg-indigo-600 text-white shadow-md shadow-indigo-200 scale-105' 
                                : 'text-slate-500 hover:bg-slate-50 hover:text-slate-700'
                            }`}
                        >
                            <span className="text-base truncate">📄</span>
                            <span className="hidden sm:inline">PDFモード</span>
                        </button>
                        <button
                            onClick={() => setMode('plaintext')}
                            className={`px-4 py-2 rounded-xl flex items-center gap-2 text-xs font-bold transition-all duration-200 ${
                                mode === 'plaintext' 
                                ? 'bg-indigo-600 text-white shadow-md shadow-indigo-200 scale-105' 
                                : 'text-slate-500 hover:bg-slate-50 hover:text-slate-700'
                            }`}
                        >
                            <span className="text-base truncate">📝</span>
                            <span className="hidden sm:inline">テキストモード</span>
                        </button>
                        <div className="w-[1px] h-6 bg-slate-200 mx-1 hidden sm:block" />
                        <button
                            onClick={() => setMode('area')}
                            className={`px-4 py-2 rounded-xl flex items-center gap-2 text-xs font-bold transition-all duration-200 ${
                                mode === 'area' 
                                ? 'bg-indigo-600 text-white shadow-md shadow-indigo-200 scale-105' 
                                : 'text-slate-500 hover:bg-slate-50 hover:text-slate-700'
                            }`}
                        >
                            <span className="text-base truncate">✂️</span>
                            <span className="hidden sm:inline">切り抜き</span>
                        </button>
                        <button
                            onClick={() => setMode('stamp')}
                            className={`px-4 py-2 rounded-xl flex items-center gap-2 text-xs font-bold transition-all duration-200 ${
                                mode === 'stamp' 
                                ? 'bg-indigo-600 text-white shadow-md shadow-indigo-200 scale-105' 
                                : 'text-slate-500 hover:bg-slate-50 hover:text-slate-700'
                            }`}
                        >
                            <span className="text-base truncate">👍</span>
                            <span className="hidden sm:inline">スタンプ</span>
                        </button>
                    </div>
                </div>
            )}

            {/* Content Area */}
            {mode === 'plaintext' ? (
                <TextModeViewer 
                    pages={pages}
                    onWordClick={handleWordClick}
                    onTextSelect={handleTextSelect}
                    jumpTarget={jumpTarget}
                    onStackPaper={onStackPaper}
                />
            ) : (
                <div className={`space-y-6 ${(mode === 'stamp' || mode === 'area') ? 'cursor-crosshair' : ''}`}>
                    {pages.map((page) => (
                        <PDFPage
                            key={page.page_num}
                            page={page}
                            onWordClick={handleWordClick}
                            onTextSelect={handleTextSelect}
                            stamps={stamps}
                            isStampMode={mode === 'stamp'}
                            onAddStamp={handleAddStamp}
                            isAreaMode={mode === 'area'}
                            onAreaSelect={handleAreaSelect}
                            onAskAI={onAskAI}
                            onStackPaper={onStackPaper}
                            jumpTarget={jumpTarget}
                        />
                    ))}
                </div>
            )}


            {status === 'processing' && (
                <div className="flex justify-center py-4">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                </div>
            )}

            {/* Stamp Palette (Only show if we have pages/paperId) */}
            {paperId && mode === 'stamp' && (
                <StampPalette
                    isStampMode={true}
                    onToggleMode={() => setMode('text')}
                    selectedStamp={selectedStamp}
                    onSelectStamp={setSelectedStamp}
                />
            )}
        </div>
    );
};

export default PDFViewer;

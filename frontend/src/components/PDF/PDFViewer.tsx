import React, { useState, useEffect, useRef } from 'react';
import { PageData } from './types';
import PDFPage from './PDFPage';
import StampPalette from '../Stamps/StampPalette';
import { Stamp, StampType } from '../Stamps/types';
import { useAuth } from '../../contexts/AuthContext';

interface PDFViewerProps {
    taskId?: string;
    initialData?: PageData[];
    uploadFile?: File | null;
    sessionId?: string;
    onWordClick?: (word: string, context?: string) => void;
}

const PDFViewer: React.FC<PDFViewerProps> = ({ uploadFile, onWordClick, sessionId }) => {
    const { token } = useAuth();
    const [pages, setPages] = useState<PageData[]>([]);
    const [status, setStatus] = useState<'idle' | 'uploading' | 'processing' | 'done' | 'error'>('idle');
    const [errorMsg, setErrorMsg] = useState<string>('');
    const eventSourceRef = useRef<EventSource | null>(null);
    const [paperId, setPaperId] = useState<string | null>(null);

    // Stamp State
    const [stamps, setStamps] = useState<Stamp[]>([]);
    const [isStampMode, setIsStampMode] = useState(false);
    const [selectedStamp, setSelectedStamp] = useState<StampType>('👍');

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

                    if (eventData.type === 'page') {
                        setPages(prev => [...prev, eventData.data]);
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

    const handleWordClick = (word: string, context?: string) => {
        if (onWordClick) {
            onWordClick(word, context);
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

            <div className={`space-y-6 ${isStampMode ? 'cursor-crosshair' : ''}`}>
                {pages.map((page) => (
                    <PDFPage
                        key={page.page_num}
                        page={page}
                        onWordClick={handleWordClick}
                        stamps={stamps}
                        isStampMode={isStampMode}
                        onAddStamp={handleAddStamp}
                    />
                ))}
            </div>

            {status === 'processing' && (
                <div className="flex justify-center py-4">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                </div>
            )}

            {/* Stamp Palette (Only show if we have pages/paperId) */}
            {paperId && (
                <StampPalette
                    isStampMode={isStampMode}
                    onToggleMode={() => setIsStampMode(!isStampMode)}
                    selectedStamp={selectedStamp}
                    onSelectStamp={setSelectedStamp}
                />
            )}
        </div>
    );
};

export default PDFViewer;



import React, { useState, useEffect, useRef } from 'react';
import { PageData } from './types';
import PDFPage from './PDFPage';

interface PDFViewerProps {
    taskId?: string; // If resuming a task
    initialData?: PageData[]; // If loading from cache
    uploadFile?: File | null;
}

const PDFViewer: React.FC<PDFViewerProps> = ({ uploadFile }) => {
    const [pages, setPages] = useState<PageData[]>([]);
    const [status, setStatus] = useState<'idle' | 'uploading' | 'processing' | 'done' | 'error'>('idle');
    const [errorMsg, setErrorMsg] = useState<string>('');
    const eventSourceRef = useRef<EventSource | null>(null);

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

    const startAnalysis = async (file: File) => {
        setStatus('uploading');
        setPages([]);

        const formData = new FormData();
        formData.append('file', file);
        formData.append('lang', 'ja'); // TODO: Make configurable
        formData.append('mode', 'json'); // Flag for JSON response

        try {
            // Step 1: Upload and get SSE URL
            // Ensure backend supports returning JSON metadata for the stream URL
            const response = await fetch('/analyze-pdf-json', { // New endpoint or modified existing
                method: 'POST',
                body: formData,
            });

            if (!response.ok) throw new Error('Upload failed');

            const data = await response.json();
            const { stream_url } = data;

            // Step 2: Connect to SSE
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
                        es.close();
                    } else if (eventData.type === 'error') {
                        setStatus('error');
                        setErrorMsg(eventData.message);
                        es.close();
                    }
                } catch (e) {
                    // Ignore non-JSON messages (keepalive etc)
                }
            };

            es.onerror = (err) => {
                console.error('SSE Error', err);
                es.close();
                // Don't set error on completion (sometimes triggers error on close)
            };

        } catch (err: any) {
            setStatus('error');
            setErrorMsg(err.message);
        }
    };

    const handleWordClick = (word: string) => {
        console.log('Word clicked:', word);
        // Dispatch custom event or callback for Dictionary lookup
        const event = new CustomEvent('lookup-word', { detail: word });
        window.dispatchEvent(event);
    };

    return (
        <div className="w-full max-w-4xl mx-auto p-4">
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

            <div className="space-y-6">
                {pages.map((page) => (
                    <PDFPage key={page.page_num} page={page} onWordClick={handleWordClick} />
                ))}
            </div>

            {status === 'processing' && (
                <div className="flex justify-center py-4">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                </div>
            )}
        </div>
    );
};

export default PDFViewer;

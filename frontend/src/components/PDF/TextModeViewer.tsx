import React, { useEffect, useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';

interface TextModeViewerProps {
    paperId: string | null;
}

const TextModeViewer: React.FC<TextModeViewerProps> = ({ paperId }) => {
    const { token } = useAuth();
    const [fullText, setFullText] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!paperId) {
            setFullText(null);
            return;
        }

        const fetchText = async () => {
            setLoading(true);
            setError(null);
            try {
                const headers: HeadersInit = {};
                if (token) headers['Authorization'] = `Bearer ${token}`;

                const res = await fetch(`/papers/${paperId}`, { headers });
                if (!res.ok) throw new Error('Failed to load text');

                const data = await res.json();
                setFullText(data.ocr_text || 'No text content available for this paper.');
            } catch (err: any) {
                console.error(err);
                setError(err.message || 'Failed to load text content');
            } finally {
                setLoading(false);
            }
        };

        fetchText();
    }, [paperId, token]);

    if (!paperId) {
        return (
            <div className="flex flex-col items-center justify-center p-12 text-slate-400">
                <p>Waiting for paper analysis...</p>
            </div>
        );
    }

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center p-20">
                <div className="animate-spin rounded-full h-10 w-10 border-4 border-indigo-100 border-t-indigo-600 mb-4"></div>
                <p className="text-slate-500 font-medium animate-pulse">Loading text content...</p>
            </div>
        );
    }

    if (error) {
        return (
            <div className="bg-red-50 border border-red-100 rounded-xl p-6 text-center">
                <p className="text-red-600 font-medium mb-2">Unavailable</p>
                <p className="text-sm text-red-500">{error}</p>
                <button 
                    onClick={() => window.location.reload()}
                    className="mt-4 text-xs bg-white border border-red-200 text-red-600 px-3 py-1 rounded hover:bg-red-50 transition-colors"
                >
                    Retry
                </button>
            </div>
        );
    }

    return (
        <div className="bg-white rounded-xl shadow-sm border border-slate-100 overflow-hidden animate-fade-in">
            {/* Header / Toolbar */}
            <div className="bg-slate-50/50 border-b border-slate-100 px-6 py-3 flex justify-between items-center">
                <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">
                        Plain Text View
                    </span>
                    <span className="bg-indigo-50 text-indigo-600 text-[10px] px-2 py-0.5 rounded-full font-medium border border-indigo-100">
                        Beta
                    </span>
                </div>
                <button
                    onClick={() => {
                        if (fullText) navigator.clipboard.writeText(fullText);
                    }}
                    className="text-slate-400 hover:text-indigo-600 transition-colors p-1.5 rounded-md hover:bg-indigo-50"
                    title="Copy full text"
                >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3" />
                    </svg>
                </button>
            </div>

            {/* Content */}
            <div className="p-8 md:p-12 max-w-4xl mx-auto">
                <article className="prose prose-slate prose-lg max-w-none font-serif leading-loose text-slate-800 break-words whitespace-pre-wrap">
                    {fullText}
                </article>
            </div>
        </div>
    );
};

export default TextModeViewer;

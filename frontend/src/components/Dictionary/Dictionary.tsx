import React, { useEffect, useState } from 'react';
import { DictionaryEntry } from './types';
import { useAuth } from '../../contexts/AuthContext';

interface DictionaryProps {
    term?: string;
    sessionId: string;
    paperId?: string | null;
    coordinates?: { page: number, x: number, y: number };
    onAskAI?: (prompt: string) => void;
    onJump?: (page: number, x: number, y: number, term?: string) => void;
}

const Dictionary: React.FC<DictionaryProps> = ({ term, sessionId, paperId, coordinates, onAskAI, onJump }) => {
    const { token } = useAuth();
    // Maintain a list of entries instead of a single one
    const [entries, setEntries] = useState<DictionaryEntry[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Reset when paperId changes (but not when transitioning from null to a real ID)
    const prevPaperIdRef = React.useRef<string | null | undefined>(paperId);

    useEffect(() => {
        if (prevPaperIdRef.current !== undefined && paperId !== prevPaperIdRef.current) {
            // If we're transitioning from null to a real ID, it means processing finished for the SAME paper.
            // In this case, we don't want to clear the entries the user might have already made.
            const isProcessingFinished = prevPaperIdRef.current === null && paperId !== null;
            
            if (!isProcessingFinished) {
                setEntries([]);
                setSavedItems(new Set());
            }
        }
        prevPaperIdRef.current = paperId;
    }, [paperId]);

    useEffect(() => {
        if (!term) return;

        // Ignore if the very last (top) entry is already this term
        if (entries.length > 0 && entries[0].word === term) {
            return;
        }

        const fetchDefinition = async () => {
            setLoading(true);
            setError(null);

            try {
                const headers: HeadersInit = {};
                if (token) headers['Authorization'] = `Bearer ${token}`;

                const res = await fetch(`/explain/${encodeURIComponent(term)}`, { headers });
                if (res.ok) {
                    const contentType = res.headers.get('content-type');
                    if (contentType && contentType.includes('application/json')) {
                        const data: DictionaryEntry = await res.json();
                        setEntries(prev => {
                            const filtered = prev.filter(e => e.word !== data.word);
                            return [data, ...filtered];
                        });
                    } else {
                        // Probably returned HTML or something else
                        setError(`Could not explain "${term}". It may be a URL or special term.`);
                    }
                } else {
                    const errorText = await res.text();
                    setError(`Definition not found: ${res.status} ${errorText.substring(0, 50)}`);
                }
            } catch (e: any) {
                console.error('Dictionary fetch error:', e);
                setError(`Failed to fetch definition for "${term}".`);
            } finally {
                setLoading(false);
            }
        };

        fetchDefinition();
    }, [term, token]); // Removed entries dependency to avoid loop, check inside setter or logic

    const [savedItems, setSavedItems] = useState<Set<string>>(new Set());

    const handleSaveToNote = async (entry: DictionaryEntry) => {
        if (!entry) return;
        try {
            const headers: HeadersInit = { 'Content-Type': 'application/json' };
            if (token) headers['Authorization'] = `Bearer ${token}`;

            const res = await fetch('/note', {
                method: 'POST',
                headers,
                body: JSON.stringify({
                    session_id: sessionId,
                    paper_id: paperId,
                    term: entry.word,
                    note: entry.translation,
                    page_number: coordinates?.page,
                    x: coordinates?.x,
                    y: coordinates?.y
                })
            });

            if (res.ok) {
                const key = entry.word;
                setSavedItems(prev => new Set(prev).add(key));
                // Fade out "Saved" status after 2 seconds
                setTimeout(() => {
                    setSavedItems(prev => {
                        const next = new Set(prev);
                        next.delete(key);
                        return next;
                    });
                }, 2000);
            }
        } catch (e) {
            console.error(e);
        }
    };


    if (entries.length === 0 && !loading && !error) {
        return (
            <div className="flex flex-col items-center justify-center h-full p-8 text-slate-300">
                <div className="bg-slate-50 p-4 rounded-xl mb-4">
                    <svg className="w-8 h-8 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                    </svg>
                </div>
                <p className="text-xs font-bold uppercase tracking-wider">Dictionary Ready</p>
                <p className="text-[10px] mt-2 text-center">Click any word in the PDF to see its definition here.</p>
            </div>
        );
    }

    return (
        <div className="p-4 h-full overflow-y-auto">
            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-4">
                Dictionary {entries.length > 0 && `(${entries.length})`}
            </h3>

            {loading && (
                <div className="animate-pulse space-y-3 mb-4">
                    <div className="h-4 bg-slate-100 rounded w-1/3"></div>
                    <div className="h-20 bg-slate-100 rounded w-full"></div>
                </div>
            )}

            {error && <div className="text-xs text-red-400 bg-red-50 p-3 rounded-lg border border-red-100 mb-4">{error}</div>}

            <div className="space-y-4">
                {entries.map((entry, index) => (
                    <div
                        key={`${entry.word}-${index}`}
                        className="bg-white p-4 rounded-xl border border-slate-100 shadow-sm animate-fade-in group transition-all hover:shadow-md"
                    >
                        <div className="flex justify-between items-start mb-3">
                            <h2 className="text-lg font-bold text-slate-800">{entry.word}</h2>
                            <div className="flex items-center gap-2">
                                <span className={`text-[9px] px-2 py-0.5 rounded-full font-bold uppercase tracking-wide
                                    ${entry.source === 'Cache' ? 'bg-purple-100 text-purple-600' :
                                        entry.source === 'LocalLM' ? 'bg-blue-100 text-blue-600' :
                                            entry.source === 'Gemini' ? 'bg-amber-100 text-amber-600' : 'bg-gray-100'
                                    }`}>
                                    {entry.source}
                                </span>
                            </div>
                        </div>

                        <p className="text-sm text-slate-600 leading-relaxed font-medium mb-4">
                            {entry.translation}
                        </p>

                        <div className="flex gap-2">
                            <button
                                onClick={() => handleSaveToNote(entry)}
                                className={`flex-1 py-2 text-xs font-bold rounded-lg transition-all flex items-center justify-center gap-2 border ${savedItems.has(entry.word)
                                    ? 'bg-green-50 text-green-600 border-green-200 cursor-default'
                                    : 'bg-slate-50 hover:bg-indigo-50 text-slate-500 hover:text-indigo-600 border-transparent group-hover:border-indigo-100'
                                    }`}
                            >
                                {savedItems.has(entry.word) ? (
                                    <>
                                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                        </svg>
                                        Saved
                                    </>
                                ) : (
                                    <>
                                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                                        </svg>
                                        Save Note
                                    </>
                                )}
                            </button>

                            {onAskAI && (
                                <button
                                    onClick={() => onAskAI('EXPLAIN THIS WORD')}
                                    className="flex-1 py-2 bg-indigo-50 hover:bg-indigo-100 text-indigo-600 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-2"
                                >
                                    <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
                                        <path d="M2 5a2 2 0 012-2h7a2 2 0 012 2v4a2 2 0 01-2 2H9l-3 3v-3H4a2 2 0 01-2-2V5z" />
                                        <path d="M15 7v2a4 4 0 01-4 4H9.828l-1.766 1.767c.28.149.599.233.938.233h2l3 3v-3h2a2 2 0 002-2V9a2 2 0 00-2-2h-1z" />
                                    </svg>
                                    <span>チャットで聞く</span>
                                </button>
                            )}

                            {onJump && coordinates && (
                                <button
                                    onClick={() => onJump(coordinates.page, coordinates.x, coordinates.y, entry.word)}
                                    className="p-2 bg-slate-50 hover:bg-slate-100 text-slate-500 rounded-lg transition-all flex items-center justify-center"
                                    title="Jump to Location"
                                >
                                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 5l7 7-7 7M5 5l7 7-7 7" />
                                    </svg>
                                </button>
                            )}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default Dictionary;

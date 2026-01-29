import React, { useEffect, useState } from 'react';
import { DictionaryEntry } from './types';
import { useAuth } from '../../contexts/AuthContext';

interface DictionaryProps {
    term?: string;
    sessionId: string;
    context?: string;
    coordinates?: { page: number, x: number, y: number };
}

const Dictionary: React.FC<DictionaryProps> = ({ term, sessionId, context, coordinates }) => {
    const { token } = useAuth();
    // Maintain a list of entries instead of a single one
    const [entries, setEntries] = useState<DictionaryEntry[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

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
                    const data: DictionaryEntry = await res.json();

                    setEntries(prev => {
                        // Remove existing entry for this word if it exists anywhere in the list
                        // so we can move it to the top (or add it fresh)
                        const filtered = prev.filter(e => e.word !== data.word);
                        return [data, ...filtered];
                    });
                } else {
                    const errorText = await res.text();
                    setError(`Definition not found: ${res.status} ${errorText}`);
                }
            } catch (e: any) {
                setError(`Failed to fetch definition: ${e.message}`);
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

    const handleRethink = async () => {
        if (!term || !context) {
            alert("No context available for this word.");
            return;
        }
        setLoading(true);
        try {
            const headers: HeadersInit = { 'Content-Type': 'application/json' };
            if (token) headers['Authorization'] = `Bearer ${token}`;

            const res = await fetch('/explain/context', {
                method: 'POST',
                headers,
                body: JSON.stringify({
                    word: term,
                    context: context.substring(0, 500), // Limit context length just in case
                    session_id: sessionId,
                    lang: 'ja'
                })
            });

            if (res.ok) {
                const data: DictionaryEntry = await res.json();
                setEntries(prev => [data, ...prev]);
            } else {
                alert("Failed to rethink with context.");
            }
        } catch (e) {
            console.error(e);
            alert("Error Rethinking.");
        } finally {
            setLoading(false);
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

            {!loading && context && term && (
                <div className="mb-4">
                    <button
                        onClick={handleRethink}
                        className="w-full py-2 bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-600 hover:to-purple-700 text-white text-xs font-bold rounded-lg shadow-sm transition-all flex items-center justify-center gap-2"
                    >
                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                        </svg>
                        Ask AI with Context
                    </button>
                    <p className="text-[9px] text-slate-400 mt-1 px-1 truncate">
                        Context: {context.substring(0, 40)}...
                    </p>
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
                                        entry.source === 'Jamdict' ? 'bg-blue-100 text-blue-600' :
                                            entry.source === 'Gemini' ? 'bg-amber-100 text-amber-600' : 'bg-gray-100'
                                    }`}>
                                    {entry.source}
                                </span>
                            </div>
                        </div>

                        <p className="text-sm text-slate-600 leading-relaxed font-medium mb-4">
                            {entry.translation}
                        </p>

                        <button
                            onClick={() => handleSaveToNote(entry)}
                            className={`w-full py-2 text-xs font-bold rounded-lg transition-all flex items-center justify-center gap-2 border ${savedItems.has(entry.word)
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
                                    Save to Notes
                                </>
                            )}
                        </button>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default Dictionary;

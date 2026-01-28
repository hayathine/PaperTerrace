import React, { useEffect, useState } from 'react';
import { DictionaryEntry } from './types';

interface DictionaryProps {
    term?: string;
    sessionId: string;
}

const Dictionary: React.FC<DictionaryProps> = ({ term, sessionId }) => {
    const [entry, setEntry] = useState<DictionaryEntry | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!term) return;

        const fetchDefinition = async () => {
            setLoading(true);
            setError(null);
            setEntry(null);
            try {
                // Use the configured proxy /explain
                const res = await fetch(`/explain/${encodeURIComponent(term)}`);
                if (res.ok) {
                    const data = await res.json();
                    setEntry(data);
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
    }, [term]);

    const handleSaveToNote = async () => {
        if (!entry || !term) return;
        try {
            await fetch('/note', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: sessionId,
                    term: entry.word,
                    note: entry.translation
                })
            });
            alert('Saved to notes!'); // Simple feedback for now
        } catch (e) {
            console.error(e);
        }
    };

    if (!term) {
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
            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-4">Definition</h3>

            {loading && (
                <div className="animate-pulse space-y-3">
                    <div className="h-4 bg-slate-100 rounded w-1/3"></div>
                    <div className="h-20 bg-slate-100 rounded w-full"></div>
                </div>
            )}

            {error && <div className="text-xs text-red-400 bg-red-50 p-3 rounded-lg border border-red-100">{error}</div>}

            {entry && (
                <div className="bg-white p-4 rounded-xl border border-slate-100 shadow-sm animate-fade-in group">
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
                        onClick={handleSaveToNote}
                        className="w-full py-2 bg-slate-50 hover:bg-indigo-50 text-slate-500 hover:text-indigo-600 text-xs font-bold rounded-lg transition-colors flex items-center justify-center gap-2 group-hover:border-indigo-100 border border-transparent"
                    >
                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                        </svg>
                        Save to Notes
                    </button>
                </div>
            )}
        </div>
    );
};

export default Dictionary;

import React, { useState } from 'react';

interface ParagraphExplainProps {
    sessionId: string;
}

const ParagraphExplain: React.FC<ParagraphExplainProps> = ({ sessionId }) => {
    const [paragraph, setParagraph] = useState('');
    const [explanation, setExplanation] = useState<string | null>(null);
    const [terms, setTerms] = useState<Record<string, string> | null>(null);
    const [loading, setLoading] = useState(false);
    const [mode, setMode] = useState<'explain' | 'terms'>('explain');

    const handleAnalyze = async () => {
        if (!paragraph) return;
        setLoading(true);
        setExplanation(null);
        setTerms(null);

        try {
            const formData = new FormData();
            formData.append('paragraph', paragraph);
            formData.append('session_id', sessionId);
            formData.append('lang', 'ja');

            const endpoint = mode === 'explain' ? '/explain-paragraph' : '/explain-terms';
            const res = await fetch(endpoint, {
                method: 'POST',
                body: formData,
            });

            if (res.ok) {
                const data = await res.json();
                if (mode === 'explain') {
                    setExplanation(data.explanation);
                } else {
                    setTerms(data.terms);
                }
            }
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex flex-col h-full p-4 overflow-y-auto">
            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-4">Deep Explain</h3>

            <div className="mb-4 space-y-3">
                <textarea
                    className="w-full p-3 text-xs border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-100 min-h-[150px]"
                    placeholder="Paste a paragraph here to analyze..."
                    value={paragraph}
                    onChange={(e) => setParagraph(e.target.value)}
                />

                <div className="flex gap-2">
                    <button
                        onClick={() => setMode('explain')}
                        className={`flex-1 py-1.5 text-[10px] font-bold uppercase tracking-wider rounded-lg transition-all ${mode === 'explain'
                                ? 'bg-indigo-600 text-white shadow-sm'
                                : 'bg-slate-100 text-slate-400 hover:bg-slate-200'
                            }`}
                    >
                        Explain
                    </button>
                    <button
                        onClick={() => setMode('terms')}
                        className={`flex-1 py-1.5 text-[10px] font-bold uppercase tracking-wider rounded-lg transition-all ${mode === 'terms'
                                ? 'bg-indigo-600 text-white shadow-sm'
                                : 'bg-slate-100 text-slate-400 hover:bg-slate-200'
                            }`}
                    >
                        Terms
                    </button>
                </div>

                <button
                    onClick={handleAnalyze}
                    disabled={!paragraph || loading}
                    className="w-full py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-bold transition-colors disabled:opacity-50"
                >
                    {loading ? 'Analyzing...' : 'Analyze Paragraph'}
                </button>
            </div>

            {explanation && (
                <div className="bg-slate-50 p-4 rounded-xl border border-slate-100 animate-fade-in">
                    <h4 className="text-xs font-bold text-slate-700 mb-2">Explanation</h4>
                    <div className="text-xs text-slate-600 leading-relaxed whitespace-pre-wrap">
                        {explanation}
                    </div>
                </div>
            )}

            {terms && (
                <div className="bg-slate-50 p-4 rounded-xl border border-slate-100 animate-fade-in space-y-3">
                    <h4 className="text-xs font-bold text-slate-700 mb-2">Technical Terms</h4>
                    {Object.entries(terms).map(([term, def]) => (
                        <div key={term} className="bg-white p-3 rounded-lg shadow-sm border border-slate-100">
                            <span className="block text-xs font-bold text-indigo-600 mb-1">{term}</span>
                            <span className="block text-[10px] text-slate-500">{def}</span>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};

export default ParagraphExplain;

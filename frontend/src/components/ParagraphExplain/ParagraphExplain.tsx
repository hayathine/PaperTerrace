import React, { useState } from 'react';

interface ParagraphExplainProps {
    sessionId: string;
}

const ParagraphExplain: React.FC<ParagraphExplainProps> = ({ sessionId }) => {
    const [paragraph, setParagraph] = useState('');
    const [explanation, setExplanation] = useState<string | null>(null);
    const [translation, setTranslation] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [mode, setMode] = useState<'explain' | 'translate'>('explain');

    const handleAnalyze = async () => {
        if (!paragraph) return;
        setLoading(true);
        setExplanation(null);
        setTranslation(null);

        try {
            const formData = new FormData();
            formData.append('paragraph', paragraph);
            formData.append('session_id', sessionId);
            formData.append('lang', 'ja'); // Could be dynamic if needed

            const endpoint = mode === 'explain' ? '/explain-paragraph' : '/translate-paragraph';
            const res = await fetch(endpoint, {
                method: 'POST',
                body: formData,
            });

            if (res.ok) {
                const data = await res.json();
                if (mode === 'explain') {
                    setExplanation(data.explanation);
                } else {
                    setTranslation(data.translation);
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
                    placeholder={mode === 'explain' ? "Paste a paragraph to analyze..." : "Paste a paragraph to translate..."}
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
                        onClick={() => setMode('translate')}
                        className={`flex-1 py-1.5 text-[10px] font-bold uppercase tracking-wider rounded-lg transition-all ${mode === 'translate'
                            ? 'bg-indigo-600 text-white shadow-sm'
                            : 'bg-slate-100 text-slate-400 hover:bg-slate-200'
                            }`}
                    >
                        Translate
                    </button>
                </div>

                <button
                    onClick={handleAnalyze}
                    disabled={!paragraph || loading}
                    className="w-full py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-bold transition-colors disabled:opacity-50"
                >
                    {loading ? 'Processing...' : (mode === 'explain' ? 'Analyze Paragraph' : 'Translate Paragraph')}
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

            {translation && (
                <div className="space-y-4 animate-fade-in">
                     <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
                        <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">Original</h4>
                        <div className="text-xs text-slate-600 leading-relaxed">
                            {paragraph}
                        </div>
                    </div>
                    <div className="bg-indigo-50 p-4 rounded-xl border border-indigo-100 shadow-sm">
                        <h4 className="text-[10px] font-bold text-indigo-400 uppercase tracking-wider mb-2">Translation</h4>
                        <div className="text-xs text-slate-700 leading-relaxed font-medium">
                            {translation}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default ParagraphExplain;

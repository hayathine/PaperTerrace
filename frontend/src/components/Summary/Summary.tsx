import React, { useState } from 'react';
import { SummaryResponse, CritiqueResponse, RadarResponse } from './types';

interface SummaryProps {
    sessionId: string;
}

type Mode = 'summary' | 'critique' | 'radar';

const Summary: React.FC<SummaryProps> = ({ sessionId }) => {
    const [mode, setMode] = useState<Mode>('summary');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const [summaryData, setSummaryData] = useState<string | null>(null);
    const [critiqueData, setCritiqueData] = useState<CritiqueResponse | null>(null);
    const [radarData, setRadarData] = useState<RadarResponse | null>(null);

    const handleSummarize = async () => {
        setLoading(true);
        setError(null);
        try {
            const formData = new FormData();
            formData.append('session_id', sessionId);
            formData.append('mode', 'full');
            formData.append('lang', 'ja');

            const res = await fetch('/summarize', { method: 'POST', body: formData });
            const data = await res.json();
            if (res.ok && data.summary) {
                setSummaryData(data.summary);
            } else {
                setError(data.error || `Summary failed: ${res.status}`);
            }
        } catch (e: any) {
            setError(`Error: ${e.message}`);
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    const handleCritique = async () => {
        setLoading(true);
        setError(null);
        try {
            const formData = new FormData();
            formData.append('session_id', sessionId);
            formData.append('lang', 'ja');
            const res = await fetch('/critique', { method: 'POST', body: formData });
            const data = await res.json();
            if (res.ok) {
                setCritiqueData(data);
            } else {
                setError(data.error || `Critique failed: ${res.status}`);
            }
        } catch (e: any) {
            setError(`Error: ${e.message}`);
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    const handleRadar = async () => {
        setLoading(true);
        setError(null);
        try {
            const formData = new FormData();
            formData.append('session_id', sessionId);
            formData.append('lang', 'ja');
            const res = await fetch('/research-radar', { method: 'POST', body: formData });
            const data = await res.json();
            if (res.ok) {
                setRadarData(data);
            } else {
                setError(data.error || `Radar scan failed: ${res.status}`);
            }
        } catch (e: any) {
            setError(`Error: ${e.message}`);
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex flex-col h-full bg-slate-50">
            <div className="flex p-2 bg-white border-b border-slate-100 gap-2 overflow-x-auto">
                <button onClick={() => setMode('summary')} className={`px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase transition-all whitespace-nowrap ${mode === 'summary' ? 'bg-indigo-50 text-indigo-600' : 'text-slate-400'}`}>Summary</button>
                <button onClick={() => setMode('critique')} className={`px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase transition-all whitespace-nowrap ${mode === 'critique' ? 'bg-red-50 text-red-600' : 'text-slate-400'}`}>Critique</button>
                <button onClick={() => setMode('radar')} className={`px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase transition-all whitespace-nowrap ${mode === 'radar' ? 'bg-emerald-50 text-emerald-600' : 'text-slate-400'}`}>Radar</button>
            </div>

            <div className="flex-1 overflow-y-auto p-4 custom-scrollbar">
                {error && (
                    <div className="mb-4 p-3 bg-red-50 border border-red-100 rounded-lg text-xs text-red-600">
                        {error}
                    </div>
                )}

                {loading && <div className="text-center py-10 text-slate-400 text-xs animate-pulse">Analyzing paper...</div>}

                {!loading && mode === 'summary' && (
                    <div className="space-y-4">
                        {!summaryData && (
                            <div className="text-center py-8">
                                <p className="text-xs text-slate-400 mb-4">Generate a comprehensive summary of the paper.</p>
                                <button onClick={handleSummarize} className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-xs font-bold shadow-sm hover:bg-indigo-700">Generate Summary</button>
                            </div>
                        )}
                        {summaryData && (
                            <div className="prose prose-sm max-w-none text-xs text-slate-600 leading-relaxed whitespace-pre-wrap bg-white p-4 rounded-xl border border-slate-100 shadow-sm">
                                {summaryData}
                            </div>
                        )}
                    </div>
                )}

                {!loading && mode === 'critique' && (
                    <div className="space-y-4">
                        {!critiqueData && (
                            <div className="text-center py-8">
                                <p className="text-xs text-slate-400 mb-4">Perform an adversarial review to find flaws.</p>
                                <button onClick={handleCritique} className="px-4 py-2 bg-red-600 text-white rounded-lg text-xs font-bold shadow-sm hover:bg-red-700">Start Critique</button>
                            </div>
                        )}
                        {critiqueData && (
                            <div className="bg-white p-4 rounded-xl border border-red-100 shadow-sm space-y-4">
                                <div className="text-xs text-slate-700 leading-relaxed">{critiqueData.overall_assessment}</div>
                                {critiqueData.hidden_assumptions && (
                                    <div className="bg-red-50 p-3 rounded-lg">
                                        <h4 className="text-[10px] font-bold text-red-800 uppercase mb-2">Hidden Assumptions</h4>
                                        <ul className="list-disc pl-4 text-[10px] text-red-700 space-y-1">
                                            {critiqueData.hidden_assumptions.map((h, i) => (
                                                <li key={i}>{h.assumption}</li>
                                            ))}
                                        </ul>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                )}

                {!loading && mode === 'radar' && (
                    <div className="space-y-4">
                        {!radarData && (
                            <div className="text-center py-8">
                                <p className="text-xs text-slate-400 mb-4">Find related papers and missing citations.</p>
                                <button onClick={handleRadar} className="px-4 py-2 bg-emerald-600 text-white rounded-lg text-xs font-bold shadow-sm hover:bg-emerald-700">Scan Radar</button>
                            </div>
                        )}
                        {radarData && radarData.related_papers && (
                            <div className="space-y-2">
                                {radarData.related_papers.map((p, i) => (
                                    <div key={i} className="bg-white p-3 rounded-lg border border-emerald-100 shadow-sm">
                                        <p className="text-xs font-bold text-slate-700">{p.title}</p>
                                        <p className="text-[10px] text-emerald-600 mt-1">{p.relevance}</p>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};

export default Summary;

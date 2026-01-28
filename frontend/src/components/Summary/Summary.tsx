import React, { useState } from 'react';
import { CritiqueResponse, RadarResponse } from './types';

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
            if (!res.ok) {
                const errorText = await res.text();
                throw new Error(errorText || `Status ${res.status}`);
            }
            const data = await res.json();
            if (data.summary) {
                setSummaryData(data.summary);
            } else {
                setError(data.error || "Summary not found in response");
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
            if (!res.ok) {
                const errorText = await res.text();
                throw new Error(errorText || `Status ${res.status}`);
            }
            const data = await res.json();
            setCritiqueData(data);
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
            if (!res.ok) {
                const errorText = await res.text();
                throw new Error(errorText || `Status ${res.status}`);
            }
            const data = await res.json();
            setRadarData(data);
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
                                <div className="text-xs text-slate-700 leading-relaxed font-medium mb-4">{critiqueData.overall_assessment}</div>

                                {critiqueData.hidden_assumptions && critiqueData.hidden_assumptions.length > 0 && (
                                    <div className="bg-red-50 p-3 rounded-lg">
                                        <h4 className="text-[10px] font-bold text-red-800 uppercase mb-2">Hidden Assumptions</h4>
                                        <div className="space-y-2">
                                            {critiqueData.hidden_assumptions.map((h, i) => (
                                                <div key={i} className="text-[10px] text-red-700">
                                                    <span className="font-bold">● {h.assumption}</span>
                                                    <p className="ml-3 opacity-80">{h.risk}</p>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {critiqueData.unverified_conditions && critiqueData.unverified_conditions.length > 0 && (
                                    <div className="bg-orange-50 p-3 rounded-lg">
                                        <h4 className="text-[10px] font-bold text-orange-800 uppercase mb-2">Unverified Conditions</h4>
                                        <div className="space-y-2">
                                            {critiqueData.unverified_conditions.map((h, i) => (
                                                <div key={i} className="text-[10px] text-orange-700">
                                                    <span className="font-bold">● {h.condition}</span>
                                                    <p className="ml-3 opacity-80">{h.impact}</p>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {critiqueData.reproducibility_risks && critiqueData.reproducibility_risks.length > 0 && (
                                    <div className="bg-slate-50 p-3 rounded-lg border border-slate-200">
                                        <h4 className="text-[10px] font-bold text-slate-800 uppercase mb-2">Reproducibility Risks</h4>
                                        <div className="space-y-2">
                                            {critiqueData.reproducibility_risks.map((h, i) => (
                                                <div key={i} className="text-[10px] text-slate-700">
                                                    <span className="font-bold">● {h.risk}</span>
                                                    <p className="ml-3 opacity-80">{h.detail}</p>
                                                </div>
                                            ))}
                                        </div>
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
                        {radarData && (
                            <div className="space-y-4">
                                {radarData.search_queries && (
                                    <div className="flex flex-wrap gap-1">
                                        {radarData.search_queries.map((q, i) => (
                                            <span key={i} className="bg-emerald-50 text-emerald-700 text-[9px] px-2 py-0.5 rounded-full border border-emerald-100 italic">"{q}"</span>
                                        ))}
                                    </div>
                                )}
                                {radarData.related_papers && radarData.related_papers.length > 0 && (
                                    <div className="space-y-2">
                                        {radarData.related_papers.map((p, i) => (
                                            <div key={i} className="bg-white p-3 rounded-lg border border-emerald-100 shadow-sm hover:shadow-md transition-shadow">
                                                <p className="text-xs font-bold text-slate-700">{p.title}</p>
                                                <div className="flex items-center gap-2 mt-1">
                                                    <span className="text-[9px] text-slate-400">{p.year || 'N/A'}</span>
                                                    {p.url && <a href={p.url} target="_blank" rel="noopener noreferrer" className="text-[9px] text-indigo-500 hover:underline">View Paper</a>}
                                                </div>
                                                {p.abstract && <p className="text-[9px] text-slate-500 mt-2 line-clamp-2 italic">{p.abstract}</p>}
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};

export default Summary;

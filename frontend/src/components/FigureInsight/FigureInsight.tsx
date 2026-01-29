import React, { useState, useEffect } from 'react';

interface FigureData {
    figure_id: string;
    image_url: string;
    explanation: string;
    caption?: string;
    page_num: number;
}

interface FigureInsightProps {
    paperId?: string | null;
}

const FigureInsight: React.FC<FigureInsightProps> = ({ paperId }) => {
    const [figures, setFigures] = useState<FigureData[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (paperId && paperId !== 'pending') {
            fetchFigures(paperId);
        } else {
            setFigures([]);
        }
    }, [paperId]);

    const fetchFigures = async (id: string) => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch(`/api/papers/${id}/figures`);
            if (res.ok) {
                const data = await res.json();
                setFigures(data.figures);
            } else {
                // If 404, maybe no figures yet
                if (res.status !== 404) {
                    setError('Failed to load figures');
                }
            }
        } catch (e) {
            setError('Error loading figures');
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex flex-col h-full bg-slate-50 relative">
            <div className="p-4 border-b border-slate-200 bg-white shadow-sm flex justify-between items-center sticky top-0 z-10">
                <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                    Figures & Charts
                </h3>
                <button 
                    onClick={() => paperId && fetchFigures(paperId)}
                    className="p-1 hover:bg-slate-100 rounded text-slate-400 hover:text-indigo-600 transition-colors"
                    title="Reload"
                >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
                </button>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-6">
                {!paperId && (
                    <div className="text-center py-10 text-slate-400">
                        <p className="text-xs">No paper selected</p>
                    </div>
                )}

                {loading && figures.length === 0 && (
                    <div className="flex justify-center py-10">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
                    </div>
                )}

                {error && (
                    <div className="text-xs text-red-500 text-center py-4 bg-red-50 rounded-lg border border-red-100">
                        {error}
                    </div>
                )}

                {!loading && figures.length === 0 && paperId && (
                    <div className="text-center py-10 text-slate-400 border-2 border-dashed border-slate-200 rounded-xl">
                        <svg className="w-12 h-12 mx-auto text-slate-300 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                        <p className="text-xs font-medium">No figures found in this paper.</p>
                    </div>
                )}

                {figures.map((fig) => (
                    <div key={fig.figure_id} className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden group hover:shadow-md transition-shadow">
                        {/* Image Container */}
                        <div className="relative bg-slate-100 aspect-video flex items-center justify-center overflow-hidden border-b border-slate-100">
                            {fig.image_url ? (
                                <img 
                                    src={fig.image_url} 
                                    alt={`Figure on page ${fig.page_num}`} 
                                    className="max-w-full max-h-full object-contain mix-blend-multiply"
                                    loading="lazy"
                                />
                            ) : (
                                <span className="text-xs text-slate-400">Image missing</span>
                            )}
                            <div className="absolute top-2 left-2 bg-black/60 text-white text-[10px] font-bold px-2 py-0.5 rounded-full backdrop-blur-sm">
                                P.{fig.page_num}
                            </div>
                        </div>

                        {/* Content */}
                        <div className="p-4">
                            {fig.explanation ? (
                                <div className="text-xs text-slate-600 leading-relaxed whitespace-pre-wrap">
                                    <span className="font-bold text-indigo-600 block mb-1">Analysis</span>
                                    {fig.explanation}
                                </div>
                            ) : (
                                <div className="flex flex-col items-center justify-center py-4 text-center">
                                    <p className="text-[10px] text-slate-400 italic mb-2">Analysis in progress...</p>
                                    <div className="h-1 w-24 bg-slate-100 rounded-full overflow-hidden">
                                        <div className="h-full bg-indigo-500/30 animate-progress"></div>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default FigureInsight;

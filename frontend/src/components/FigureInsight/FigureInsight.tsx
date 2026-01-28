import React, { useState } from 'react';



const FigureInsight: React.FC = () => {
    const [file, setFile] = useState<File | null>(null);
    const [caption, setCaption] = useState('');
    const [analysis, setAnalysis] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            setFile(e.target.files[0]);
            setAnalysis(null);
        }
    };

    const handleAnalyze = async () => {
        if (!file) return;

        setLoading(true);
        setError(null);
        try {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('caption', caption);

            const res = await fetch('/analyze-figure', {
                method: 'POST',
                body: formData,
            });

            if (res.ok) {
                const data = await res.json();
                setAnalysis(data.analysis);
            } else {
                setError('Failed to analyze figure');
            }
        } catch (e) {
            setError(String(e));
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex flex-col h-full p-4 overflow-y-auto">
            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-4">Figure Insight</h3>

            <div className="mb-4 space-y-3">
                <input
                    type="file"
                    accept="image/*"
                    onChange={handleFileChange}
                    className="block w-full text-xs text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-xs file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100"
                />

                {file && (
                    <div className="relative rounded-lg overflow-hidden border border-slate-200">
                        <img
                            src={URL.createObjectURL(file)}
                            alt="Preview"
                            className="w-full h-auto max-h-48 object-contain bg-slate-50"
                        />
                    </div>
                )}

                <textarea
                    className="w-full p-2 text-xs border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-100"
                    placeholder="Enter caption or context (optional)..."
                    rows={3}
                    value={caption}
                    onChange={(e) => setCaption(e.target.value)}
                />

                <button
                    onClick={handleAnalyze}
                    disabled={!file || loading}
                    className="w-full py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-bold transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    {loading ? 'Analyzing...' : 'Analyze Figure'}
                </button>
            </div>

            {error && <div className="text-xs text-red-500 mb-2">{error}</div>}

            {analysis && (
                <div className="bg-slate-50 p-4 rounded-xl border border-slate-100 animate-fade-in">
                    <h4 className="text-xs font-bold text-slate-700 mb-2">Analysis Result</h4>
                    <div className="text-xs text-slate-600 space-y-2 whitespace-pre-wrap leading-relaxed">
                        {analysis}
                    </div>
                </div>
            )}
        </div>
    );
};

export default FigureInsight;

import React, { useMemo } from 'react';
import { PageData } from './types';
import StampOverlay from '../Stamps/StampOverlay';
import { Stamp } from '../Stamps/types';

interface PDFPageProps {
    page: PageData;
    scale?: number;
    onWordClick?: (word: string) => void;
    // Stamp props
    stamps?: Stamp[];
    isStampMode?: boolean;
    onAddStamp?: (page: number, x: number, y: number) => void;
}

const PDFPage: React.FC<PDFPageProps> = ({
    page,
    onWordClick,
    stamps = [],
    isStampMode = false,
    onAddStamp
}) => {
    const { width, height, words, image_url, page_num } = page;

    // Filter stamps for this page
    const pageStamps = useMemo(() => {
        return stamps.filter(s => s.page_number === page_num || !s.page_number);
    }, [stamps, page_num]);

    const handleAddStamp = (x: number, y: number) => {
        if (onAddStamp) {
            onAddStamp(page_num, x, y);
        }
    };

    return (
        <div className="relative mb-8 shadow-2xl rounded-xl overflow-hidden bg-white transition-all duration-300 border border-slate-200/50 mx-auto" style={{ maxWidth: '100%' }}>
            {/* Header / Page Number */}
            <div className="bg-gray-50 border-b border-gray-100 px-4 py-2 flex justify-between items-center">
                <span className="text-xs font-bold text-gray-400 uppercase tracking-widest">
                    Page {page.page_num}
                </span>
            </div>

            {/* Image Container */}
            <div className="relative w-full">
                <img
                    src={image_url}
                    alt={`Page ${page.page_num}`}
                    className="w-full h-auto block select-none"
                    loading="lazy"
                />

                {/* Stamp Overlay */}
                <StampOverlay
                    stamps={pageStamps}
                    isStampMode={isStampMode}
                    onAddStamp={handleAddStamp}
                />

                {/* Word Overlays */}
                <div className="absolute inset-0 w-full h-full z-10">
                    {words.map((w, idx) => {
                        const [x1, y1, x2, y2] = w.bbox;
                        const w_width = x2 - x1;
                        const w_height = y2 - y1;

                        const left = (x1 / width) * 100;
                        const top = (y1 / height) * 100;
                        const styleW = (w_width / width) * 100;
                        const styleH = (w_height / height) * 100;

                        return (
                            <div
                                key={`${idx}`}
                                className={`absolute rounded-sm group ${!isStampMode ? 'cursor-pointer hover:bg-yellow-300/30' : 'pointer-events-none'}`}
                                style={{
                                    left: `${left}%`,
                                    top: `${top}%`,
                                    width: `${styleW}%`,
                                    height: `${styleH}%`,
                                }}
                                onClick={() => !isStampMode && onWordClick && onWordClick(w.word)}
                                title={w.word}
                            />
                        );
                    })}
                </div>
            </div>
        </div>
    );
};

export default PDFPage;

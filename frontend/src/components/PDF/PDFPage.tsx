import React from 'react';
import { PageData } from './types';

interface PDFPageProps {
    page: PageData;
    scale?: number;
    onWordClick?: (word: string) => void;
}

const PDFPage: React.FC<PDFPageProps> = ({ page, onWordClick }) => {
    const { width, height, words, image_url } = page;

    // Calculate percentages for responsive overlay
    // bbox is assumed to be [x1, y1, x2, y2] relative to width/height

    return (
        <div className="relative mb-8 shadow-md rounded-lg overflow-hidden bg-white transition-transform mx-auto" style={{ maxWidth: '100%' }}>
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

                {/* Word Overlays */}
                <div className="absolute inset-0 w-full h-full">
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
                                className="absolute cursor-pointer hover:bg-yellow-300/30 rounded-sm group z-10"
                                style={{
                                    left: `${left}%`,
                                    top: `${top}%`,
                                    width: `${styleW}%`,
                                    height: `${styleH}%`,
                                }}
                                onClick={() => onWordClick && onWordClick(w.word)}
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

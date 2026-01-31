import { PageData, PageWithLines, LineData } from './types';

/**
 * Groups words into lines based on coordinates and column detection.
 * Memoization should be handled by the caller.
 */
export function groupWordsIntoLines(pages: PageData[]): PageWithLines[] {
    return pages.map(page => {
        const words = page.words;
        if (!words || words.length === 0) return { ...page, lines: [] } as PageWithLines;

        // 1. Detect Columns (Simple heuristic: find if there's a large gap in X coordinates)
        const sortedByX = [...words].sort((a, b) => a.bbox[0] - b.bbox[0]);
        const columns: (typeof words)[] = [];
        let currentColumn: typeof words = [];

        // A gap of more than 10% of page width often indicates a new column
        const columnGapThreshold = page.width * 0.1;

        sortedByX.forEach((word, i) => {
            if (i > 0 && word.bbox[0] - sortedByX[i-1].bbox[2] > columnGapThreshold) {
                columns.push(currentColumn);
                currentColumn = [word];
            } else {
                currentColumn.push(word);
            }
        });
        columns.push(currentColumn);

        // 2. For each column, group words into lines
        const allLines: LineData[] = [];

        columns.forEach(colWords => {
            // Sort by Y for line grouping within this column
            const sortedByY = colWords.sort((a, b) => (a.bbox[1] - b.bbox[1]) || (a.bbox[0] - b.bbox[0]));
            const colLines: LineData[] = [];

            sortedByY.forEach(word => {
                const wordY1 = word.bbox[1];
                const wordHeight = word.bbox[3] - word.bbox[1];
                
                // Find if word belongs to an existing line in this column
                const line = colLines.find(l => Math.abs(wordY1 - l.bbox[1]) < wordHeight * 0.4);
                
                if (line) {
                    line.words.push(word);
                    line.bbox[0] = Math.min(line.bbox[0], word.bbox[0]);
                    line.bbox[1] = Math.min(line.bbox[1], word.bbox[1]);
                    line.bbox[2] = Math.max(line.bbox[2], word.bbox[2]);
                    line.bbox[3] = Math.max(line.bbox[3], word.bbox[3]);
                } else {
                    colLines.push({ words: [word], bbox: [...word.bbox] });
                }
            });

            // Sort words within each line by X
            colLines.forEach(line => line.words.sort((a, b) => a.bbox[0] - b.bbox[0]));
            allLines.push(...colLines);
        });

        return { ...page, lines: allLines };
    });
}

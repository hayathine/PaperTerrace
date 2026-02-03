import { PageData, PageWithLines, LineData } from "./types";

/**
 * Groups words into lines based on coordinates and column detection.
 * Memoization should be handled by the caller.
 */
export function groupWordsIntoLines(pages: PageData[]): PageWithLines[] {
  return pages.map((page) => {
    const validWords = (page.words || []).filter(
      (w) => w && w.bbox && w.bbox.length >= 4,
    );
    if (validWords.length === 0) return { ...page, lines: [] } as PageWithLines;

    const sortedByX = [...validWords].sort(
      (a, b) => (a.bbox[0] || 0) - (b.bbox[0] || 0),
    );
    const columns: (typeof validWords)[] = [];
    let currentColumn: typeof validWords = [];

    const pageWidth = page.width || 1000;
    const columnGapThreshold = pageWidth * 0.1;

    sortedByX.forEach((word, i) => {
      if (
        i > 0 &&
        word.bbox[0] - sortedByX[i - 1].bbox[2] > columnGapThreshold
      ) {
        columns.push(currentColumn);
        currentColumn = [word];
      } else {
        currentColumn.push(word);
      }
    });
    columns.push(currentColumn);

    // 2. For each column, group words into lines
    const allLines: LineData[] = [];

    columns.forEach((colWords) => {
      // Sort by Y for line grouping within this column
      const sortedByY = colWords.sort(
        (a, b) => a.bbox[1] - b.bbox[1] || a.bbox[0] - b.bbox[0],
      );
      const colLines: LineData[] = [];

      sortedByY.forEach((word) => {
        const wordY1 = word.bbox[1];
        const wordHeight = word.bbox[3] - word.bbox[1];

        // Find if word belongs to an existing line in this column
        const line = colLines.find(
          (l) => Math.abs(wordY1 - l.bbox[1]) < wordHeight * 0.4,
        );

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
      colLines.forEach((line) =>
        line.words.sort((a, b) => a.bbox[0] - b.bbox[0]),
      );
      allLines.push(...colLines);
    });

    return { ...page, lines: allLines };
  });
}

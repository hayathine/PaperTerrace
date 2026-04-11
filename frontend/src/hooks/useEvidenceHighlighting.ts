import { useEffect, useState } from "react";
import type { Grounding } from "../components/Chat/types";
import type { PageData } from "../components/PDF/types";

type HighlightRect = { x: number; y: number; width: number; height: number };

/**
 * チャットの evidence grounding からPDFページ上のハイライト座標を計算し、
 * 最初の証拠ページへ自動スクロールするカスタムフック。
 */
export function useEvidenceHighlighting(
	evidence: Grounding | undefined,
	pages: PageData[],
) {
	const [evidenceHighlights, setEvidenceHighlights] = useState<
		Record<number, HighlightRect[]>
	>({});

	useEffect(() => {
		if (!evidence || !pages.length) {
			setEvidenceHighlights({});
			return;
		}

		const highlights: Record<number, HighlightRect[]> = {};

		if (evidence.supports) {
			for (const support of evidence.supports) {
				const text = support.segment_text;
				if (!text || text.length < 5) continue;

				const tokens = text
					.toLowerCase()
					.split(/\s+/)
					.filter((t: string) => t.length > 0);
				if (tokens.length === 0) continue;

				for (const page of pages) {
					for (let i = 0; i <= (page.words?.length || 0) - tokens.length; i++) {
						let match = true;
						for (let j = 0; j < tokens.length; j++) {
							if (!page.words[i + j].word.toLowerCase().includes(tokens[j])) {
								match = false;
								break;
							}
						}
						if (match) {
							const matchedWords = page.words.slice(i, i + tokens.length);
							const x1 = Math.min(...matchedWords.map((w) => w.bbox[0]));
							const y1 = Math.min(...matchedWords.map((w) => w.bbox[1]));
							const x2 = Math.max(...matchedWords.map((w) => w.bbox[2]));
							const y2 = Math.max(...matchedWords.map((w) => w.bbox[3]));

							if (!highlights[page.page_num]) highlights[page.page_num] = [];
							highlights[page.page_num].push({
								x: x1 / (page.width || 1),
								y: y1 / (page.height || 1),
								width: (x2 - x1) / (page.width || 1),
								height: (y2 - y1) / (page.height || 1),
							});
							if (highlights[page.page_num].length > 5) break;
						}
					}
				}
			}
		}

		setEvidenceHighlights(highlights);

		// 最初の証拠ページへ自動スクロール
		const firstPage = Object.keys(highlights).sort(
			(a, b) => Number(a) - Number(b),
		)[0];
		if (firstPage) {
			const p = Number(firstPage);
			setTimeout(() => {
				document
					.getElementById(`page-${p}`)
					?.scrollIntoView({ behavior: "smooth", block: "center" });
			}, 100);
		}
	}, [evidence, pages]);

	return { evidenceHighlights };
}

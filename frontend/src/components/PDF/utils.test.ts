import { describe, expect, it } from "vitest";
import type { PageData } from "./types";
import { groupWordsIntoLines } from "./utils";

describe("groupWordsIntoLines", () => {
	it("should group words into lines for a single page", () => {
		const mockPage: PageData = {
			page_num: 1,
			image_url: "test.png",
			width: 1000,
			height: 1000,
			words: [
				{ word: "Hello", bbox: [100, 100, 150, 120] },
				{ word: "World", bbox: [160, 100, 210, 120] },
				{ word: "Second", bbox: [100, 150, 150, 170] },
				{ word: "Line", bbox: [160, 150, 210, 170] },
			],
		};

		const results = groupWordsIntoLines([mockPage]);

		expect(results).toHaveLength(1);
		const pageWithLines = results[0];
		expect(pageWithLines.lines).toHaveLength(2);

		// First line should have 'Hello' and 'World'
		expect(pageWithLines.lines[0].words).toHaveLength(2);
		expect(pageWithLines.lines[0].words[0].word).toBe("Hello");
		expect(pageWithLines.lines[0].words[1].word).toBe("World");

		// Second line should have 'Second' and 'Line'
		expect(pageWithLines.lines[1].words).toHaveLength(2);
		expect(pageWithLines.lines[1].words[0].word).toBe("Second");
		expect(pageWithLines.lines[1].words[1].word).toBe("Line");
	});

	it("should return empty lines if no words are provided", () => {
		const mockPage: PageData = {
			page_num: 1,
			image_url: "test.png",
			width: 1000,
			height: 1000,
			words: [],
		};

		const results = groupWordsIntoLines([mockPage]);
		expect(results[0].lines).toHaveLength(0);
	});
});

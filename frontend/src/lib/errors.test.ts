import { describe, expect, it } from "vitest";
import { ERROR_KEYS } from "./errors";

describe("ERROR_KEYS", () => {
	it("should have common error keys", () => {
		expect(ERROR_KEYS.common.unexpected).toBe("common.errors.unexpected");
		expect(ERROR_KEYS.common.network).toBe("common.errors.network");
	});

	it("should have figure error keys", () => {
		expect(ERROR_KEYS.figure.analysisFailed).toBe(
			"viewer.figure_analysis_failed",
		);
	});
});

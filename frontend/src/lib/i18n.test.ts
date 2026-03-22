import { describe, expect, it } from "vitest";
import i18n from "./i18n";

describe("i18n configuration", () => {
	it("should initialize i18next correctly", () => {
		expect(i18n.isInitialized).toBe(true);
	});

	it("should have resources for 'ja' and 'en'", () => {
		expect(i18n.hasResourceBundle("ja", "translation")).toBe(true);
		expect(i18n.hasResourceBundle("en", "translation")).toBe(true);
	});

	it("should have a valid language set", () => {
		expect(i18n.language).toBeDefined();
		expect(typeof i18n.language).toBe("string");
	});

	it("should translate common keys in Japanese", async () => {
		await i18n.changeLanguage("ja");
		expect(i18n.t("common.loading")).toBe("読み込み中...");
	});

	it("should translate common keys in English", async () => {
		await i18n.changeLanguage("en");
		expect(i18n.t("common.loading")).toBe("Loading...");
	});
});

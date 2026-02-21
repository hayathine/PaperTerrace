import i18n from "i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import { initReactI18next } from "react-i18next";
import en from "../locales/en.json";
import ja from "../locales/ja.json";

i18n
	.use(LanguageDetector)
	.use(initReactI18next)
	.init({
		resources: {
			ja: { translation: ja },
			en: { translation: en },
		},
		fallbackLng: "ja",
		interpolation: {
			escapeValue: false,
		},
		detection: {
			order: ["querystring", "cookie", "localStorage", "navigator", "htmlTag"],
			caches: ["localStorage", "cookie"],
		},
	});

export default i18n;

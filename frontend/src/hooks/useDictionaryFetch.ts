import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { API_URL } from "@/config";
import { buildAuthHeaders } from "@/lib/auth";
import { createLogger } from "@/lib/logger";
import type { DictionaryEntryWithCoords } from "../components/Dictionary/Dictionary";

const log = createLogger("useDictionaryFetch");

type SubTab = "translation" | "explanation" | "figures" | "history";

interface UseDictionaryFetchDeps {
	term: string | undefined;
	sessionId: string;
	paperId: string | null | undefined;
	context: string | undefined;
	conf: number | undefined;
	imageUrl: string | undefined;
	currentSubTab: SubTab;
	token: string | null;
	paperTitleRef: React.RefObject<string | undefined>;
	onSubTabChange?: (tab: SubTab) => void;
}

export function useDictionaryFetch({
	term,
	sessionId,
	paperId,
	context,
	conf,
	imageUrl,
	currentSubTab,
	token,
	paperTitleRef,
	onSubTabChange,
}: UseDictionaryFetchDeps) {
	const { t, i18n } = useTranslation();
	const lang = i18n.language.startsWith("ja") ? "ja" : "en";

	const [entries, setEntries] = useState<DictionaryEntryWithCoords[]>([]);
	const [explanationEntries, setExplanationEntries] = useState<
		DictionaryEntryWithCoords[]
	>([]);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [isTruncated, setIsTruncated] = useState(false);

	// paperId 変化時のリセット（null → 実IDへの遷移はスキップ）
	const prevPaperIdRef = useRef<string | null | undefined>(paperId);
	useEffect(() => {
		if (
			prevPaperIdRef.current !== undefined &&
			paperId !== prevPaperIdRef.current
		) {
			const isProcessingFinished =
				prevPaperIdRef.current === null && paperId !== null;
			if (!isProcessingFinished) {
				setEntries([]);
				setExplanationEntries([]);
			}
		}
		prevPaperIdRef.current = paperId;
	}, [paperId]);

	// サブタブのみが変わった場合（term 変化なし）にフェッチが走らないよう前回値を追跡
	const prevTermRef = useRef<string | undefined>(undefined);

	useEffect(() => {
		const termChanged = prevTermRef.current !== term;
		prevTermRef.current = term;

		if (!term) return;

		if (!termChanged && currentSubTab === "explanation") return;

		const isLink = (s: string) => {
			const clean = s.trim();
			if (clean.includes(" ") || clean.includes("\n")) return false;
			return (
				/^(https?:\/\/|\/\/|www\.)/i.test(clean) ||
				clean.includes("doi.org/") ||
				/\.[a-z]{2,}\//i.test(clean)
			);
		};

		if (isLink(term)) {
			setEntries([]);
			setExplanationEntries([]);
			return;
		}

		const targetEntries =
			currentSubTab === "explanation" ? explanationEntries : entries;
		if (targetEntries.length > 0 && targetEntries[0].word === term) return;

		const setter =
			currentSubTab === "explanation" ? setExplanationEntries : setEntries;

		const fetchDefinition = async () => {
			setLoading(true);
			setError(null);
			setIsTruncated(false);

			const tempEntry: DictionaryEntryWithCoords = {
				word: term,
				translation: "...",
				source: "Analyzing",
				is_analyzing: true,
			};
			if (imageUrl) tempEntry.image_url = imageUrl;
			setter((prev) => [tempEntry, ...prev.filter((e) => e.word !== term)]);

			try {
				const headers = buildAuthHeaders(token);
				let res: Response;

				if (imageUrl) {
					res = await fetch(`${API_URL}/api/explain/image`, {
						method: "POST",
						headers: { ...headers, "Content-Type": "application/json" },
						body: JSON.stringify({
							image_url: imageUrl,
							prompt: term || "この画像を解説してください",
							session_id: sessionId,
							paper_id: paperId || "",
							lang,
						}),
					});
				} else if (currentSubTab === "explanation" && context) {
					res = await fetch(`${API_URL}/api/explain/context`, {
						method: "POST",
						headers: { ...headers, "Content-Type": "application/json" },
						body: JSON.stringify({
							word: term,
							context,
							session_id: sessionId,
							lang,
						}),
					});
				} else if (term.length > 50) {
					const truncatedWord =
						term.length > 2000 ? `${term.slice(0, 2000)}…` : term;
					const rawContext = context || term;
					const truncatedContext =
						rawContext.length > 5000
							? `${rawContext.slice(0, 5000)}…`
							: rawContext;
					if (truncatedWord !== term || truncatedContext !== rawContext) {
						setIsTruncated(true);
					}
					if (currentSubTab === "explanation") {
						res = await fetch(`${API_URL}/api/explain/context`, {
							method: "POST",
							headers: { ...headers, "Content-Type": "application/json" },
							body: JSON.stringify({
								word: truncatedWord,
								context: truncatedContext,
								session_id: sessionId,
								lang,
							}),
						});
					} else {
						res = await fetch(`${API_URL}/api/translate`, {
							method: "POST",
							headers: { ...headers, "Content-Type": "application/json" },
							body: JSON.stringify({
								word: truncatedWord,
								context: truncatedContext,
								session_id: sessionId,
								paper_id: paperId || "",
								paper_title: paperTitleRef.current,
								lang,
							}),
						});
					}
				} else {
					const queryParams = new URLSearchParams({
						lang,
						paper_id: paperId || "",
						session_id: sessionId || "",
					});
					if (paperTitleRef.current)
						queryParams.append("paper_title", paperTitleRef.current);
					if (context) queryParams.append("context", context);
					if (conf !== undefined && conf !== null)
						queryParams.append("conf", conf.toString());

					res = await fetch(
						`${API_URL}/api/translate/${encodeURIComponent(term)}?${queryParams.toString()}`,
						{ headers },
					);
				}

				if (res.ok) {
					const contentType = res.headers.get("content-type");
					if (contentType?.includes("application/json")) {
						const data: DictionaryEntryWithCoords = await res.json();
						setter((prev) => [
							data,
							...prev.filter((e) => e.word !== data.word),
						]);
					} else {
						log.warn("fetch_definition", "Non-JSON response for term", {
							term,
						});
						setError(t("viewer.dictionary.error_unavailable"));
						setter((prev) =>
							prev.filter((e) => e.word !== term || !e.is_analyzing),
						);
					}
				} else {
					const errorText = await res.text();
					log.error("fetch_definition", "Definition not found", {
						status: res.status,
						error: errorText,
						term,
					});
					setError(t("viewer.dictionary.error_unavailable"));
					setter((prev) =>
						prev.filter((e) => e.word !== term || !e.is_analyzing),
					);
				}
			} catch (e: unknown) {
				log.error("fetch_definition", "Dictionary fetch error", {
					error: e,
					term,
				});
				setError(t("viewer.dictionary.error_unavailable"));
				setter((prev) =>
					prev.filter((e) => e.word !== term || !e.is_analyzing),
				);
			} finally {
				setLoading(false);
			}
		};

		fetchDefinition();
	}, [
		term,
		token,
		imageUrl,
		sessionId,
		paperId,
		context,
		conf,
		i18n.language,
		currentSubTab,
	]);

	const handleDeepTranslate = useCallback(
		async (entry: DictionaryEntryWithCoords) => {
			if (!entry) return;

			onSubTabChange?.("explanation");

			const originalTranslation =
				!entry.is_analyzing && entry.translation !== "..."
					? entry.translation
					: undefined;

			setExplanationEntries((prev) => {
				const exists = prev.some((e) => e.word === entry.word);
				const updated = {
					...entry,
					is_analyzing: true,
					source_translation: originalTranslation,
				};
				if (exists)
					return prev.map((e) => (e.word === entry.word ? updated : e));
				return [updated, ...prev];
			});
			setLoading(true);
			setError(null);

			try {
				const headers = buildAuthHeaders(token, {
					"Content-Type": "application/json",
				});

				let res: Response;
				if (context) {
					res = await fetch(`${API_URL}/api/explain/context`, {
						method: "POST",
						headers,
						body: JSON.stringify({
							word: entry.word,
							context,
							session_id: sessionId,
							lang,
						}),
					});
				} else {
					res = await fetch(
						`${API_URL}/api/translate-deep/${encodeURIComponent(entry.word)}?lang=${lang}&paper_id=${paperId || ""}&session_id=${sessionId || ""}`,
						{ headers },
					);
				}

				if (res.ok) {
					const data: DictionaryEntryWithCoords = await res.json();
					data.source_translation = originalTranslation;
					setExplanationEntries((prev) =>
						prev.map((e) =>
							e.word === entry.word ? { ...data, is_analyzing: false } : e,
						),
					);
				} else {
					const errorText = await res.text();
					log.error("deep_translate", "Translation failed", {
						status: res.status,
						error: errorText,
						term: entry.word,
					});
					setError(t("viewer.dictionary.error_translation_unavailable"));
					setExplanationEntries((prev) =>
						prev.map((e) =>
							e.word === entry.word ? { ...e, is_analyzing: false } : e,
						),
					);
				}
			} catch (e: unknown) {
				log.error("deep_translate", "Translation failed", {
					error: e,
					term: entry.word,
				});
				setError(t("viewer.dictionary.error_translation_unavailable"));
				setExplanationEntries((prev) =>
					prev.map((e) =>
						e.word === entry.word ? { ...e, is_analyzing: false } : e,
					),
				);
			} finally {
				setLoading(false);
			}
		},
		[context, sessionId, paperId, token, lang, t, onSubTabChange],
	);

	return {
		entries,
		setEntries,
		explanationEntries,
		setExplanationEntries,
		loading,
		error,
		isTruncated,
		handleDeepTranslate,
	};
}

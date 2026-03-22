import React, { useCallback, useEffect, useState } from "react";
import type { DictionaryEntry } from "./types";

export type DictionaryEntryWithCoords = DictionaryEntry & {
	coords?: { page: number; x: number; y: number };
	image_url?: string;
	is_analyzing?: boolean;
};

import { useTranslation } from "react-i18next";
import { API_URL } from "@/config";
import { createLogger } from "@/lib/logger";
import { useAuth } from "../../contexts/AuthContext";
import CopyButton from "../Common/CopyButton";
import FeedbackSection from "../Common/FeedbackSection";
import MarkdownContent from "../Common/MarkdownContent";
import FigureInsight from "../FigureInsight/FigureInsight";
import type { SelectedFigure } from "../PDF/types";

const log = createLogger("Dictionary");

interface SavedNote {
	note_id: string;
	term: string;
	note: string;
	page_number?: number;
	created_at?: string;
}

interface DictionaryProps {
	term?: string;
	sessionId: string;
	paperId?: string | null;
	context?: string;
	coordinates?: { page: number; x: number; y: number };
	conf?: number;
	onJump?: (page: number, x: number, y: number, term?: string) => void;
	imageUrl?: string;
	onAskInChat?: () => void;
	selectedFigure?: SelectedFigure | null;
	subTab?: "translation" | "explanation" | "figures" | "history";
	onSubTabChange?: (
		tab: "translation" | "explanation" | "figures" | "history",
	) => void;
}

const Dictionary: React.FC<DictionaryProps> = ({
	term,
	sessionId,
	paperId,
	context,
	coordinates,
	conf,
	onJump,
	imageUrl,
	onAskInChat,
	selectedFigure,
	subTab = "translation",
	onSubTabChange,
}) => {
	const { t, i18n } = useTranslation();
	const { token } = useAuth();

	// Sub-tab is controlled from parent (App.tsx -> Sidebar.tsx)
	// No local state needed for activeSubTab to avoid sync issues/double fetches
	const currentSubTab = subTab || "translation";

	// 内部変更を親に通知
	const handleSubTabChange = (
		tab: "translation" | "explanation" | "figures" | "history",
	) => {
		onSubTabChange?.(tab);
	};

	// 保存済み用語一覧（historyタブ用）
	const [savedNotes, setSavedNotes] = useState<SavedNote[]>([]);

	// 図が選択されたら自動的に figures サブタブへ切り替え (Parent logic in App.tsx handles this)
	// but we keep a local check for robustness if needed, however it's better to let App.tsx handle it.
	// Actually, handleFigureSelect in App.tsx already sets dictSubTab to "figures".

	// Separate translation and explanation entries
	const [entries, setEntries] = useState<DictionaryEntryWithCoords[]>([]);
	const [explanationEntries, setExplanationEntries] = useState<
		DictionaryEntryWithCoords[]
	>([]);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);

	// Reset when paperId changes (but not when transitioning from null to a real ID)
	const prevPaperIdRef = React.useRef<string | null | undefined>(paperId);

	useEffect(() => {
		if (
			prevPaperIdRef.current !== undefined &&
			paperId !== prevPaperIdRef.current
		) {
			// If we're transitioning from null to a real ID, it means processing finished for the SAME paper.
			// In this case, we don't want to clear the entries the user might have already made.
			const isProcessingFinished =
				prevPaperIdRef.current === null && paperId !== null;

			if (!isProcessingFinished) {
				setEntries([]);
				setExplanationEntries([]);
				setSavedItems(new Set());
			}
		}
		prevPaperIdRef.current = paperId;
	}, [paperId]);

	// サブタブのみが変わった場合（term 変化なし）にフェッチが走らないよう前回値を追跡する
	const prevTermRef = React.useRef<string | undefined>(undefined);
	const prevSubTabRef = React.useRef<
		"translation" | "explanation" | "figures" | "history"
	>("translation");

	useEffect(() => {
		const termChanged = prevTermRef.current !== term;
		prevTermRef.current = term;
		prevSubTabRef.current = currentSubTab;

		if (!term) return;

		// サブタブのみが変わった場合（term 変化なし）に解説タブで自動フェッチしない
		// 解説は単語クリック時（term 変化あり）のみ自動実行する
		if (!termChanged && currentSubTab === "explanation") return;

		const isLink = (s: string) => {
			const clean = s.trim();
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

		// Use currentSubTab (derived from subTab prop)
		const targetEntries =
			currentSubTab === "explanation" ? explanationEntries : entries;
		if (targetEntries.length > 0 && targetEntries[0].word === term) {
			return;
		}

		const fetchDefinition = async () => {
			setLoading(true);

			setError(null);

			// Add a temporary entry to show analyzing indicator for the new word
			const tempEntry: DictionaryEntryWithCoords = {
				word: term,
				translation: "...",
				source: "Analyzing",
				is_analyzing: true,
				coords: coordinates,
			};
			if (imageUrl) tempEntry.image_url = imageUrl;

			const setter =
				currentSubTab === "explanation" ? setExplanationEntries : setEntries;
			setter((prev) => {
				const filtered = prev.filter((e) => e.word !== term);
				return [tempEntry, ...filtered];
			});

			try {
				const headers: HeadersInit = {};
				if (token) headers.Authorization = `Bearer ${token}`;

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
							lang: i18n.language,
						}),
					});
				} else if (currentSubTab === "explanation" && context) {
					// Use context-aware explanation for the explanation tab
					res = await fetch(`${API_URL}/api/explain/context`, {
						method: "POST",
						headers: { ...headers, "Content-Type": "application/json" },
						body: JSON.stringify({
							word: term,
							context: context,
							session_id: sessionId,
							lang: i18n.language,
						}),
					});
				} else if (term.length > 50) {
					// 長文テキスト（文章・段落）はPOSTエンドポイントで処理
					// GETパスパラメータに長文を含めると500エラーになるため
					if (currentSubTab === "explanation") {
						res = await fetch(`${API_URL}/api/explain/context`, {
							method: "POST",
							headers: { ...headers, "Content-Type": "application/json" },
							body: JSON.stringify({
								word: term,
								context: context || term,
								session_id: sessionId,
								lang: i18n.language,
							}),
						});
					} else {
						res = await fetch(`${API_URL}/api/translate`, {
							method: "POST",
							headers: { ...headers, "Content-Type": "application/json" },
							body: JSON.stringify({
								word: term,
								context: context || term,
								session_id: sessionId,
								paper_id: paperId || "",
								lang: i18n.language,
							}),
						});
					}
				} else {
					const queryParams = new URLSearchParams({
						lang: i18n.language,
						paper_id: paperId || "",
						session_id: sessionId || "",
					});
					if (context) {
						queryParams.append("context", context);
					}
					if (conf !== undefined && conf !== null) {
						queryParams.append("conf", conf.toString());
					}

					res = await fetch(
						`${API_URL}/api/translate/${encodeURIComponent(term)}?${queryParams.toString()}`,
						{ headers },
					);
				}

				if (res.ok) {
					const contentType = res.headers.get("content-type");
					if (contentType?.includes("application/json")) {
						const data: DictionaryEntryWithCoords = await res.json();
						data.coords = coordinates; // Attach current coordinates
						if (imageUrl) data.image_url = imageUrl;

						const setter =
							currentSubTab === "explanation"
								? setExplanationEntries
								: setEntries;
						setter((prev) => {
							const filtered = prev.filter((e) => e.word !== data.word);
							return [data, ...filtered];
						});
					} else {
						// Probably returned HTML or something else
						log.warn("fetch_definition", "Non-JSON response for term", {
							term,
						});
						setError(t("viewer.dictionary.error_unavailable"));
						const setter =
							currentSubTab === "explanation"
								? setExplanationEntries
								: setEntries;
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
					const setter =
						currentSubTab === "explanation"
							? setExplanationEntries
							: setEntries;
					setter((prev) =>
						prev.filter((e) => e.word !== term || !e.is_analyzing),
					);
				}
			} catch (e: any) {
				log.error("fetch_definition", "Dictionary fetch error", {
					error: e,
					term,
				});

				setError(t("viewer.dictionary.error_unavailable"));
				const setter =
					currentSubTab === "explanation" ? setExplanationEntries : setEntries;
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
	]); // Removed entries dependency to avoid loop, check inside setter or logic

	const [savedItems, setSavedItems] = useState<Set<string>>(new Set());

	const fetchSavedNotes = useCallback(async () => {
		try {
			const headers: HeadersInit = {};
			if (token) headers.Authorization = `Bearer ${token}`;

			const baseUrl = API_URL || window.location.origin;
			const url = new URL(`/api/note/${sessionId}`, baseUrl);
			if (paperId) url.searchParams.append("paper_id", paperId);

			const res = await fetch(url.toString(), { headers });
			if (res.ok) {
				const data = await res.json();
				if (data.notes) {
					const terms = data.notes.map((n: any) => n.term);
					setSavedItems(new Set(terms));
					// termがあるもの（辞書保存）のみ用語一覧に格納
					const termNotes = data.notes.filter((n: any) => n.term);
					setSavedNotes(termNotes);
				}
			}
		} catch (e) {
			log.error("fetch_saved_notes", "Dictionary fetchSavedNotes error", {
				error: e,
			});
		}
	}, [sessionId, paperId, token]);

	useEffect(() => {
		if (sessionId && paperId) {
			fetchSavedNotes();
		}

		const handleNotesUpdated = () => {
			if (sessionId && paperId) fetchSavedNotes();
		};

		window.addEventListener("notes-updated", handleNotesUpdated);
		return () => {
			window.removeEventListener("notes-updated", handleNotesUpdated);
		};
	}, [sessionId, paperId, fetchSavedNotes]);

	const handleDeepTranslate = useCallback(
		async (entry: DictionaryEntryWithCoords) => {
			if (!entry) return;

			// Switch to explanation tab
			onSubTabChange?.("explanation");

			// Always use explanationEntries setter for "AI解説" results
			const setter = setExplanationEntries;

			const updateEntry = (updates: Partial<DictionaryEntryWithCoords>) =>
				setter((prev) => {
					const exists = prev.some((e) => e.word === entry.word);
					if (exists) {
						return prev.map((e) =>
							e.word === entry.word ? { ...e, ...updates } : e,
						);
					}
					// If it doesn't exist in explanation tab yet, add it
					return [{ ...entry, ...updates }, ...prev];
				});

			updateEntry({ is_analyzing: true });
			setLoading(true);
			setError(null);

			try {
				const headers: HeadersInit = { "Content-Type": "application/json" };
				if (token) headers.Authorization = `Bearer ${token}`;

				let res: Response;
				if (context) {
					res = await fetch(`${API_URL}/api/explain/context`, {
						method: "POST",
						headers,
						body: JSON.stringify({
							word: entry.word,
							context: context,
							session_id: sessionId,
							lang: i18n.language,
						}),
					});
				} else {
					res = await fetch(
						`${API_URL}/api/translate-deep/${encodeURIComponent(entry.word)}?lang=${i18n.language}&paper_id=${paperId || ""}&session_id=${sessionId || ""}`,
						{ headers },
					);
				}

				if (res.ok) {
					const data: DictionaryEntryWithCoords = await res.json();
					data.coords = entry.coords;
					setter((prev) =>
						prev.map((e) =>
							e.word === entry.word ? { ...data, is_analyzing: false } : e,
						),
					);
				} else {
					const errorText = await res.text();
					log.error("deep_translate", "Translation failed with status", {
						status: res.status,
						error: errorText,
						term: entry.word,
					});
					setError(t("viewer.dictionary.error_translation_unavailable"));
					updateEntry({ is_analyzing: false });
				}
			} catch (e) {
				log.error("deep_translate", "Translation failed", {
					error: e,
					term: entry.word,
				});
				setError(t("viewer.dictionary.error_translation_unavailable"));
				updateEntry({ is_analyzing: false });
			} finally {
				setLoading(false);
			}
		},
		[currentSubTab, context, sessionId, paperId, token, i18n.language, t],
	);

	const handleSaveToNote = async (entry: DictionaryEntryWithCoords) => {
		if (!entry) return;
		const targetCoords = entry.coords || coordinates;
		try {
			const headers: HeadersInit = { "Content-Type": "application/json" };
			if (token) headers.Authorization = `Bearer ${token}`;

			const res = await fetch(`${API_URL}/api/note`, {
				method: "POST",
				headers,
				body: JSON.stringify({
					session_id: sessionId,
					paper_id: paperId,
					term: entry.word,
					note: entry.translation,
					page_number: targetCoords?.page,
					x: targetCoords?.x,
					y: targetCoords?.y,
				}),
			});

			if (res.ok) {
				const key = entry.word;
				setSavedItems((prev) => new Set(prev).add(key));
				window.dispatchEvent(new Event("notes-updated"));
			}
		} catch (e) {
			log.error("save_to_note", "Failed to save note", {
				error: e,
				term: entry.word,
			});
		}
	};

	const isUrl =
		term &&
		(/^(https?:\/\/|\/\/|www\.)/i.test(term) || term.includes("doi.org/"));

	const activeEntries =
		currentSubTab === "explanation" ? explanationEntries : entries;

	let content: React.ReactNode;
	if (activeEntries.length === 0 && !loading && !error) {
		if (isUrl) {
			content = (
				<div className="flex flex-col items-center justify-center h-full p-8 text-slate-300">
					<div className="bg-orange-50 p-4 rounded-xl mb-4 text-orange-400">
						<svg
							className="w-8 h-8"
							fill="none"
							viewBox="0 0 24 24"
							stroke="currentColor"
						>
							<path
								strokeLinecap="round"
								strokeLinejoin="round"
								strokeWidth={2}
								d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"
							/>
						</svg>
					</div>
					<p className="text-xs font-bold uppercase tracking-wider text-slate-400">
						{t("viewer.dictionary.external_link")}
					</p>

					<p className="text-[10px] mt-2 text-center text-slate-400 break-all max-w-[160px] sm:max-w-[200px]">
						{term}
					</p>
					<div className="flex flex-col gap-2 mt-6 w-full">
						<button
							type="button"
							onClick={() =>
								window.open(
									term.startsWith("//")
										? `https:${term}`
										: term.startsWith("www")
											? `https://${term}`
											: term,
									"_blank",
								)
							}
							className="w-full py-2 bg-orange-600 hover:bg-orange-700 text-white rounded-lg text-xs font-bold transition-all"
						>
							{t("viewer.dictionary.open_link")}
						</button>
					</div>
				</div>
			);
		} else {
			content = (
				<div className="flex flex-col items-center justify-center h-full p-8 text-slate-300">
					<div className="bg-slate-50 p-4 rounded-xl mb-4">
						<svg
							className="w-8 h-8 opacity-50"
							fill="none"
							viewBox="0 0 24 24"
							stroke="currentColor"
						>
							<path
								strokeLinecap="round"
								strokeLinejoin="round"
								strokeWidth={2}
								d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
							/>
						</svg>
					</div>
					<p className="text-xs font-bold uppercase tracking-wider">
						{t("viewer.dictionary.ready")}
					</p>
					<p className="text-[10px] mt-2 text-center">
						{t("viewer.dictionary.click_hint")}
					</p>
				</div>
			);
		}
	} else {
		content = (
			<div
				className="p-4 flex-1 overflow-y-auto"
				style={{ WebkitOverflowScrolling: "touch" }}
			>
				{loading && activeEntries.length === 0 && (
					<div className="flex flex-col items-center justify-center py-12 animate-in fade-in duration-500">
						<div className="relative w-12 h-12 mb-4">
							<div className="absolute inset-0 rounded-full border-4 border-orange-100"></div>
							<div className="absolute inset-0 rounded-full border-4 border-orange-500 border-t-transparent animate-spin"></div>
						</div>
						<p className="text-sm font-bold text-slate-600 animate-pulse">
							{t("summary.processing")}
						</p>
						<p className="text-[10px] text-slate-400 mt-1">
							{t("common.loading_description")}
						</p>
					</div>
				)}

				{error && (
					<div className="text-xs text-red-400 bg-red-50 p-3 rounded-lg border border-red-100 mb-4">
						{error}
					</div>
				)}

				<div className="space-y-4">
					{activeEntries.map((entry, index) => (
						<div
							key={`${entry.word}-${index}`}
							className={`bg-white p-3 sm:p-4 rounded-xl border border-slate-100 shadow-sm animate-fade-in group transition-all hover:shadow-md relative overflow-hidden ${entry.is_analyzing ? "opacity-90" : ""}`}
						>
							{entry.is_analyzing && (
								<div className="absolute inset-0 z-50 bg-white/60 backdrop-blur-[1px] flex flex-col items-center justify-center animate-in fade-in duration-300">
									<div className="w-6 h-6 border-2 border-orange-500 border-t-transparent rounded-full animate-spin mb-2"></div>
									<span className="text-[10px] font-bold text-orange-600 uppercase tracking-wider animate-pulse">
										{t("summary.processing")}
									</span>
								</div>
							)}
							<div className="flex justify-between items-start mb-3">
								<div className="text-sm font-semibold text-slate-800 leading-relaxed">
									{entry.word}
								</div>
								<div className="flex items-center gap-2">
									<CopyButton
										text={`${entry.word}\n${entry.translation}`}
										size={12}
									/>
									<span
										className={`text-[9px] px-2 py-0.5 rounded-full font-bold uppercase tracking-wide
                                    ${
																			entry.source === "Cache"
																				? "bg-amber-100 text-amber-600"
																				: entry.source === "LocalLM"
																					? "bg-blue-100 text-blue-600"
																					: entry.source === "Gemini"
																						? "bg-amber-100 text-amber-600"
																						: "bg-gray-100"
																		}`}
									>
										{entry.source}
									</span>
								</div>
							</div>

							{entry.image_url && (
								<div className="mb-4 rounded-xl overflow-hidden border border-slate-200">
									<img
										src={entry.image_url}
										alt="Figure"
										className="w-full h-auto object-contain bg-slate-50"
									/>
								</div>
							)}

							<MarkdownContent className="prose prose-sm max-w-none text-sm text-slate-600 leading-relaxed font-medium mb-4">
								{entry.translation}
							</MarkdownContent>

							<div className="flex gap-2">
								<button
									type="button"
									onClick={() => handleSaveToNote(entry)}
									disabled={savedItems.has(entry.word)}
									className={`flex-1 py-2.5 sm:py-2 text-xs font-bold rounded-lg transition-all flex items-center justify-center gap-2 border ${
										savedItems.has(entry.word)
											? "bg-green-50 text-green-600 border-green-200 cursor-default"
											: "bg-slate-50 hover:bg-slate-100 text-slate-500 border-transparent group-hover:border-slate-200"
									}`}
								>
									{savedItems.has(entry.word) ? (
										<>
											<svg
												className="w-3 h-3"
												fill="none"
												viewBox="0 0 24 24"
												stroke="currentColor"
											>
												<path
													strokeLinecap="round"
													strokeLinejoin="round"
													strokeWidth={2}
													d="M5 13l4 4L19 7"
												/>
											</svg>
											{t("viewer.dictionary.saved")}
										</>
									) : (
										<>
											<svg
												className="w-3 h-3"
												fill="none"
												viewBox="0 0 24 24"
												stroke="currentColor"
											>
												<path
													strokeLinecap="round"
													strokeLinejoin="round"
													strokeWidth={2}
													d="M12 4v16m8-8H4"
												/>
											</svg>
											{t("viewer.dictionary.save_note")}
										</>
									)}
								</button>

								{entry.image_url ? (
									<button
										type="button"
										onClick={() => onAskInChat?.()}
										className="flex-1 py-2.5 sm:py-2 bg-blue-50 hover:bg-blue-100 text-blue-600 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-2"
									>
										<svg
											className="w-3.5 h-3.5"
											fill="none"
											viewBox="0 0 24 24"
											stroke="currentColor"
										>
											<path
												strokeLinecap="round"
												strokeLinejoin="round"
												strokeWidth={2}
												d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
											/>
										</svg>
										<span>{t("viewer.dictionary.ask_in_chat")}</span>
									</button>
								) : (
									<button
										type="button"
										onClick={() => handleDeepTranslate(entry)}
										className="flex-1 py-2.5 sm:py-2 bg-slate-50 hover:bg-slate-100 text-orange-600 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-2"
									>
										<svg
											className="w-3.5 h-3.5"
											fill="none"
											viewBox="0 0 24 24"
											stroke="currentColor"
										>
											<path
												strokeLinecap="round"
												strokeLinejoin="round"
												strokeWidth={2}
												d="M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129"
											/>
										</svg>
										<span>{t("viewer.dictionary.ask_ai")}</span>
									</button>
								)}

								{(onJump && entry.coords) || (onJump && coordinates) ? (
									<button
										type="button"
										onClick={() => {
											const c = entry.coords || coordinates;
											if (c) onJump(c.page, c.x, c.y, entry.word);
										}}
										className="px-3 py-2 bg-slate-50 hover:bg-slate-100 text-slate-500 rounded-lg text-xs font-bold transition-all flex items-center justify-center"
										title="Jump to Location"
									>
										JUMP
									</button>
								) : null}
							</div>

							<div className="mt-2 pl-1 pr-1">
								<FeedbackSection
									sessionId={sessionId}
									targetType="translation"
									targetId={entry.word}
									traceId={entry.trace_id}
								/>
							</div>
						</div>
					))}
				</div>
			</div>
		);
	}

	const historyContent = (
		<div
			className="p-3 flex-1 overflow-y-auto"
			style={{ WebkitOverflowScrolling: "touch" }}
		>
			{savedNotes.length === 0 ? (
				<div className="flex flex-col items-center justify-center h-full p-8 text-slate-300">
					<div className="bg-slate-50 p-4 rounded-xl mb-4">
						<svg
							className="w-8 h-8 opacity-50"
							fill="none"
							viewBox="0 0 24 24"
							stroke="currentColor"
						>
							<path
								strokeLinecap="round"
								strokeLinejoin="round"
								strokeWidth={2}
								d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
							/>
						</svg>
					</div>
					<p className="text-xs font-bold uppercase tracking-wider">
						{t("viewer.dictionary.history_empty")}
					</p>
					<p className="text-[10px] mt-2 text-center">
						{t("viewer.dictionary.history_hint")}
					</p>
				</div>
			) : (
				<div className="space-y-2">
					{savedNotes.map((note) => (
						<button
							key={note.note_id}
							type="button"
							onClick={() => {
								handleSubTabChange("translation");
								onSubTabChange?.("translation");
							}}
							className="w-full text-left bg-white border border-slate-100 rounded-xl p-3 hover:shadow-md hover:border-orange-200 transition-all group"
						>
							<div className="flex items-start justify-between gap-2">
								<span className="text-sm font-bold text-slate-800 group-hover:text-orange-600 transition-colors truncate">
									{note.term}
								</span>
								{note.page_number != null && (
									<span className="text-[9px] bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded-full shrink-0">
										p.{note.page_number}
									</span>
								)}
							</div>
							<p className="text-[11px] text-slate-500 mt-1 line-clamp-2 leading-relaxed">
								{note.note}
							</p>
						</button>
					))}
				</div>
			)}
		</div>
	);

	return (
		<div className="flex flex-col h-full overflow-hidden bg-white">
			{/* Sub-tab Navigation */}
			<div className="flex px-4 pt-2 border-b border-slate-100 bg-white sticky top-0 z-20 shrink-0 overflow-x-auto">
				<button
					type="button"
					onClick={() => handleSubTabChange("translation")}
					className={`pb-2 px-1 text-xs font-bold border-b-2 uppercase tracking-wider transition-all shrink-0 ${
						currentSubTab === "translation"
							? "text-orange-600 border-orange-600"
							: "text-slate-400 hover:text-slate-600 border-transparent"
					}`}
				>
					{t("sidebar.tabs.translation")}{" "}
					{entries.length > 0 && `(${entries.length})`}
				</button>
				<button
					type="button"
					onClick={() => handleSubTabChange("explanation")}
					className={`ml-6 pb-2 px-1 text-xs font-bold border-b-2 uppercase tracking-wider transition-all shrink-0 ${
						currentSubTab === "explanation"
							? "text-orange-600 border-orange-600"
							: "text-slate-400 hover:text-slate-600 border-transparent"
					}`}
				>
					{t("sidebar.tabs.explanation")}{" "}
					{explanationEntries.length > 0 && `(${explanationEntries.length})`}
				</button>
				<button
					type="button"
					onClick={() => handleSubTabChange("figures")}
					className={`ml-6 pb-2 px-1 text-xs font-bold border-b-2 uppercase tracking-wider transition-all shrink-0 ${
						currentSubTab === "figures"
							? "text-orange-600 border-orange-600"
							: "text-slate-400 hover:text-slate-600 border-transparent"
					}`}
				>
					{t("sidebar.tabs.figures")}
				</button>
				<button
					type="button"
					onClick={() => handleSubTabChange("history")}
					className={`ml-6 pb-2 px-1 text-xs font-bold border-b-2 uppercase tracking-wider transition-all shrink-0 ${
						currentSubTab === "history"
							? "text-orange-600 border-orange-600"
							: "text-slate-400 hover:text-slate-600 border-transparent"
					}`}
				>
					{t("sidebar.tabs.history")}{" "}
					{savedNotes.length > 0 && `(${savedNotes.length})`}
				</button>
			</div>

			<div
				className="flex-1 overflow-y-auto"
				style={{ WebkitOverflowScrolling: "touch" }}
			>
				{currentSubTab === "translation" || currentSubTab === "explanation" ? (
					content
				) : currentSubTab === "history" ? (
					historyContent
				) : (
					<div className="p-4">
						<FigureInsight
							selectedFigure={selectedFigure}
							sessionId={sessionId}
						/>
					</div>
				)}
			</div>
		</div>
	);
};

export default Dictionary;

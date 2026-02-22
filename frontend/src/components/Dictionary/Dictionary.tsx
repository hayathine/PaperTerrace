import React, { useEffect, useState } from "react";
import type { DictionaryEntry } from "./types";

export type DictionaryEntryWithCoords = DictionaryEntry & {
	coords?: { page: number; x: number; y: number };
};

import { useTranslation } from "react-i18next";
import { API_URL } from "../../config";
import { useAuth } from "../../contexts/AuthContext";

interface DictionaryProps {
	term?: string;
	sessionId: string;
	paperId?: string | null;
	context?: string;
	coordinates?: { page: number; x: number; y: number };
	onJump?: (page: number, x: number, y: number, term?: string) => void;
}

const Dictionary: React.FC<DictionaryProps> = ({
	term,
	sessionId,
	paperId,
	context,
	coordinates,
	onJump,
}) => {
	const { t, i18n } = useTranslation();
	const { token } = useAuth();

	// Maintain a list of entries instead of a single one
	const [entries, setEntries] = useState<DictionaryEntryWithCoords[]>([]);
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
				setSavedItems(new Set());
			}
		}
		prevPaperIdRef.current = paperId;
	}, [paperId]);

	useEffect(() => {
		if (!term) return;

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
			return;
		}

		// Ignore if the very last (top) entry is already this term
		if (entries.length > 0 && entries[0].word === term) {
			return;
		}

		const fetchDefinition = async () => {
			setLoading(true);

			setError(null);

			try {
				const headers: HeadersInit = {};
				if (token) headers.Authorization = `Bearer ${token}`;

				const res = await fetch(
					`${API_URL}/api/explain/${encodeURIComponent(term)}?lang=${i18n.language}&paper_id=${paperId || ""}`,
					{ headers },
				);

				if (res.ok) {
					const contentType = res.headers.get("content-type");
					if (contentType?.includes("application/json")) {
						const data: DictionaryEntryWithCoords = await res.json();
						data.coords = coordinates; // Attach current coordinates
						setEntries((prev) => {
							const filtered = prev.filter((e) => e.word !== data.word);
							return [data, ...filtered];
						});
					} else {
						// Probably returned HTML or something else
						setError(
							`Could not explain "${term}". It may be a URL or special term.`,
						);
					}
				} else {
					const errorText = await res.text();
					setError(
						`Definition not found: ${res.status} ${errorText.substring(0, 50)}`,
					);
				}
			} catch (e: any) {
				console.error("Dictionary fetch error:", e);
				setError(`Failed to fetch definition for "${term}".`);
			} finally {
				setLoading(false);
			}
		};

		fetchDefinition();
	}, [term, token]); // Removed entries dependency to avoid loop, check inside setter or logic

	const [savedItems, setSavedItems] = useState<Set<string>>(new Set());

	const handleDeepTranslate = async (entry: DictionaryEntryWithCoords) => {
		if (!entry) return;
		setLoading(true);
		setError(null);

		try {
			const headers: HeadersInit = { "Content-Type": "application/json" };
			if (token) headers.Authorization = `Bearer ${token}`;

			let res: Response;
			if (context) {
				// Use context-aware explanation
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
				// Use simple explanation (with paper summary context from backend)
				res = await fetch(
					`${API_URL}/api/explain-deep/${encodeURIComponent(entry.word)}?lang=${i18n.language}&paper_id=${paperId || ""}`,
					{ headers },
				);
			}

			if (res.ok) {
				const data: DictionaryEntryWithCoords = await res.json();
				data.coords = entry.coords; // Preserve coordinates
				setEntries((prev) =>
					prev.map((e) => (e.word === entry.word ? data : e)),
				);
			} else {
				const errorText = await res.text();
				setError(`Translation failed: ${res.status} ${errorText}`);
			}
		} catch (e) {
			console.error(e);
			setError("Translation failed.");
		} finally {
			setLoading(false);
		}
	};

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
				// Fade out "Saved" status after 2 seconds
				setTimeout(() => {
					setSavedItems((prev) => {
						const next = new Set(prev);
						next.delete(key);
						return next;
					});
				}, 2000);
			}
		} catch (e) {
			console.error(e);
		}
	};

	if (entries.length === 0 && !loading && !error) {
		const isUrl =
			term &&
			(/^(https?:\/\/|\/\/|www\.)/i.test(term) || term.includes("doi.org/"));

		if (isUrl) {
			return (
				<div className="flex flex-col items-center justify-center h-full p-8 text-slate-300">
					<div className="bg-indigo-50 p-4 rounded-xl mb-4 text-indigo-400">
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

					<p className="text-[10px] mt-2 text-center text-slate-400 break-all max-w-[200px]">
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
							className="w-full py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-bold transition-all"
						>
							{t("viewer.dictionary.open_link")}
						</button>
					</div>
				</div>
			);
		}

		return (
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

	return (
		<div className="p-4 h-full overflow-y-auto">
			<h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-4">
				{t("sidebar.tabs.dict")} {entries.length > 0 && `(${entries.length})`}
			</h3>

			{loading && (
				<div className="animate-pulse space-y-3 mb-4">
					<div className="h-4 bg-slate-100 rounded w-1/3"></div>
					<div className="h-20 bg-slate-100 rounded w-full"></div>
				</div>
			)}

			{error && (
				<div className="text-xs text-red-400 bg-red-50 p-3 rounded-lg border border-red-100 mb-4">
					{error}
				</div>
			)}

			<div className="space-y-4">
				{entries.map((entry, index) => (
					<div
						key={`${entry.word}-${index}`}
						className="bg-white p-4 rounded-xl border border-slate-100 shadow-sm animate-fade-in group transition-all hover:shadow-md"
					>
						<div className="flex justify-between items-start mb-3">
							<h2 className="text-lg font-bold text-slate-800">{entry.word}</h2>
							<div className="flex items-center gap-2">
								<span
									className={`text-[9px] px-2 py-0.5 rounded-full font-bold uppercase tracking-wide
                                    ${
																			entry.source === "Cache"
																				? "bg-purple-100 text-purple-600"
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

						<p className="text-sm text-slate-600 leading-relaxed font-medium mb-4">
							{entry.translation}
						</p>

						<div className="flex gap-2">
							<button
								type="button"
								onClick={() => handleSaveToNote(entry)}
								disabled={savedItems.has(entry.word)}
								className={`flex-1 py-2 text-xs font-bold rounded-lg transition-all flex items-center justify-center gap-2 border ${
									savedItems.has(entry.word)
										? "bg-green-50 text-green-600 border-green-200 cursor-default"
										: "bg-slate-50 hover:bg-indigo-50 text-slate-500 hover:text-indigo-600 border-transparent group-hover:border-indigo-100"
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

							<button
								type="button"
								onClick={() => handleDeepTranslate(entry)}
								className="flex-1 py-2 bg-indigo-50 hover:bg-indigo-100 text-indigo-600 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-2"
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
					</div>
				))}
			</div>
		</div>
	);
};

export default Dictionary;

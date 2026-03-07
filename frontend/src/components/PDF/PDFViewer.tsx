import type React from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { API_URL } from "@/config";
import { createLogger } from "@/lib/logger";
import { useAuth } from "../../contexts/AuthContext";
import { usePaperCache } from "../../db/hooks";
// TODO (suspended): db import used by handleAreaSelect - restore when area mode re-enabled.
// import { db } from "../../db";
import { isDbAvailable } from "../../db/index";
import PDFPage from "./PDFPage";
import TextModeViewer from "./TextModeViewer";
import type { PageData, PageWithLines, SelectedFigure } from "./types";
import { groupWordsIntoLines } from "./utils";

const log = createLogger("PDFViewer");

interface PDFViewerProps {
	taskId?: string;
	initialData?: PageData[];
	uploadFile?: File | null;
	sessionId?: string;
	onWordClick?: (
		word: string,
		context?: string,
		coords?: { page: number; x: number; y: number },
		conf?: number,
	) => void;
	onTextSelect?: (
		text: string,
		coords: { page: number; x: number; y: number },
	) => void;
	onAreaSelect?: (
		imageUrl: string,
		coords: { page: number; x: number; y: number },
	) => void;
	jumpTarget?: { page: number; x: number; y: number; term?: string } | null;
	onStatusChange?: (
		status: "idle" | "uploading" | "processing" | "done" | "error",
	) => void;
	onPaperLoaded?: (paperId: string | null) => void;
	onAskAI?: (
		prompt: string,
		imageUrl?: string,
		coords?: any,
		originalText?: string,
		contextText?: string,
	) => void;
	onFigureSelect?: (figure: SelectedFigure) => void;
	paperId?: string | null;
	// 検索関連props
	searchTerm?: string;
	onSearchMatchesUpdate?: (
		matches: Array<{ page: number; wordIndex: number }>,
	) => void;
	currentSearchMatch?: { page: number; wordIndex: number } | null;
	evidence?: any;
	appEnv?: string;
	mode?: "text" | "stamp" | "area" | "plaintext";
}

const PDFViewer: React.FC<PDFViewerProps> = ({
	uploadFile,
	paperId: propPaperId,
	onWordClick,
	onTextSelect,
	// TODO (suspended): onAreaSelect prop kept for interface compatibility, not forwarded.
	// onAreaSelect,
	sessionId,
	jumpTarget,
	onStatusChange,
	onPaperLoaded,
	onAskAI,
	onFigureSelect,
	searchTerm,
	onSearchMatchesUpdate,
	currentSearchMatch,
	evidence,
	appEnv = "production",
	mode: externalMode,
}) => {
	const { t, i18n } = useTranslation();
	const { token, isGuest } = useAuth();
	const isDev = appEnv === "development";
	const {
		getCachedPaper,
		savePaperToCache,
		cachePaperImages,
		deleteCorruptedCache,
	} = usePaperCache();
	// syncStatus lifted to App.tsx
	const [pages, setPages] = useState<PageData[]>([]);
	const [status, setStatus] = useState<
		"idle" | "uploading" | "processing" | "done" | "error"
	>("idle");
	const [errorMsg, setErrorMsg] = useState<string>("");
	const eventSourceRef = useRef<EventSource | null>(null);
	const [loadedPaperId, setLoadedPaperId] = useState<string | null>(null);
	const processingFileRef = useRef<File | null>(null);
	const activeTaskIdRef = useRef<string | null>(null);

	// Use external mode if provided, otherwise fallback to internal (though App.tsx now provides it)
	const [internalMode] = useState<"text" | "stamp" | "area" | "plaintext">(
		"plaintext",
	);
	const mode = externalMode ?? internalMode;

	// PDF ページグリッド（クリック/スタンプ/エリアモード用）の遅延マウント。
	const [hasMountedPdfMode, setHasMountedPdfMode] = useState(false);

	// TODO (suspended): stamp state removed. Restore for stamp mode.

	const pagesRef = useRef<PageData[]>([]);
	const [evidenceHighlights, setEvidenceHighlights] = useState<
		Record<number, any[]>
	>({});

	useEffect(() => {
		if (onStatusChange) {
			onStatusChange(status);
		}
	}, [status, onStatusChange]);

	useEffect(() => {
		if (!evidence || !pages.length) {
			setEvidenceHighlights({});
			return;
		}

		const highlights: Record<number, any[]> = {};

		if (evidence.supports) {
			evidence.supports.forEach((support: any) => {
				const text = support.segment_text;
				if (!text || text.length < 5) return;

				const tokens = text
					.toLowerCase()
					.split(/\s+/)
					.filter((t: string) => t.length > 0);
				if (tokens.length === 0) return;

				pages.forEach((page) => {
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
							// To avoid too many highlights for the same segment, we can break after some matches
							if (highlights[page.page_num].length > 5) break;
						}
					}
				});
			});
		}

		setEvidenceHighlights(highlights);

		// Auto-scroll to first evidence
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

	// Sync ref with state
	useEffect(() => {
		pagesRef.current = pages;
	}, [pages]);

	// PDF グリッドの遅延マウント: plaintext 以外のモードに初めて切り替えた時のみ実行
	useEffect(() => {
		if (mode !== "plaintext" && !hasMountedPdfMode) {
			setHasMountedPdfMode(true);
		}
	}, [mode, hasMountedPdfMode]);

	// 検索マッチング処理
	useEffect(() => {
		if (!searchTerm || searchTerm.length < 2 || !onSearchMatchesUpdate) {
			if (onSearchMatchesUpdate) {
				onSearchMatchesUpdate([]);
			}
			return;
		}

		const lowerSearchTerm = searchTerm.toLowerCase();
		const matches: Array<{ page: number; wordIndex: number }> = [];

		pages.forEach((page) => {
			if (page.words) {
				page.words.forEach((word, wordIndex) => {
					if (word.word.toLowerCase().includes(lowerSearchTerm)) {
						matches.push({
							page: page.page_num,
							wordIndex,
						});
					}
				});
			}
		});

		onSearchMatchesUpdate(matches);
	}, [searchTerm, pages, onSearchMatchesUpdate]);

	// 現在の検索マッチ位置へスクロール
	useEffect(() => {
		if (!currentSearchMatch) return;

		const pageId =
			mode === "plaintext"
				? `text-page-${currentSearchMatch.page}`
				: `page-${currentSearchMatch.page}`;
		const pageEl = document.getElementById(pageId);
		if (!pageEl) return;

		const scroller = pageEl.closest(".overflow-y-auto");
		const matchEl = document.getElementById("current-search-match");

		if (scroller) {
			if (matchEl) {
				const matchRect = matchEl.getBoundingClientRect();
				const scrollerRect = scroller.getBoundingClientRect();
				const currentScrollTop = scroller.scrollTop;
				const matchTopInScroller =
					currentScrollTop + (matchRect.top - scrollerRect.top);

				scroller.scrollTo({
					top: matchTopInScroller - 100,
					behavior: "smooth",
				});
			} else {
				const pageRect = pageEl.getBoundingClientRect();
				const scrollerRect = scroller.getBoundingClientRect();
				const currentScrollTop = scroller.scrollTop;
				const pageTopInScroller =
					currentScrollTop + (pageRect.top - scrollerRect.top);

				scroller.scrollTo({
					top: pageTopInScroller - 100,
					behavior: "smooth",
				});
			}
		} else {
			if (matchEl) {
				matchEl.scrollIntoView({ behavior: "smooth", block: "center" });
			} else {
				pageEl.scrollIntoView({ behavior: "smooth", block: "start" });
			}
		}
	}, [currentSearchMatch, mode]);

	// Handle file upload and paper loading
	// Use isMounted to handle React StrictMode double-mounting
	useEffect(() => {
		let isMounted = true;

		const initiate = async () => {
			// Small delay to avoid StrictMode race condition
			await new Promise((r) => setTimeout(r, 10));
			if (!isMounted) return;

			if (uploadFile) {
				startAnalysis(uploadFile);
			} else if (propPaperId && propPaperId !== loadedPaperId) {
				loadExistingPaper(propPaperId);
			}
		};

		initiate();

		return () => {
			isMounted = false;
			// Only close if there's no active task (avoid closing mid-stream)
			if (eventSourceRef.current && !activeTaskIdRef.current) {
				eventSourceRef.current.close();
				eventSourceRef.current = null;
			}
		};
	}, [uploadFile, propPaperId]);

	// Fetch stamps when loadedPaperId is available
	useEffect(() => {
		// TODO (suspended): fetchStamps(loadedPaperId) removed - stamp mode suspended.
		if (onPaperLoaded) {
			onPaperLoaded(loadedPaperId);
		}
	}, [loadedPaperId]);

	const triggerLazyLayoutAnalysis = async (
		paperId: string,
		initialPages?: PageData[],
	) => {
		try {
			// Prefer explicitly passed pages so callers don't have to wait for
			// pagesRef to sync (useEffect runs after render, so pagesRef.current
			// may still be stale when called immediately after setPages()).
			const finalPages = initialPages ?? pagesRef.current;
			if (!finalPages || finalPages.length === 0) return;

			const BATCH_SIZE = 10;
			const totalPages = finalPages.length;

			for (let startIdx = 0; startIdx < totalPages; startIdx += BATCH_SIZE) {
				const endIdx = Math.min(startIdx + BATCH_SIZE, totalPages);
				const batchPages = finalPages
					.slice(startIdx, endIdx)
					.map((p) => p.page_num);

				log.info("trigger_lazy_layout_analysis", "Triggering batch analysis", {
					pages: batchPages,
				});

				const headers: HeadersInit = {
					"Content-Type": "application/x-www-form-urlencoded",
				};
				if (token) headers.Authorization = `Bearer ${token}`;

				const formData = new URLSearchParams();
				formData.append("paper_id", paperId);
				formData.append("page_numbers", batchPages.join(","));

				// Important for transient sessions: provide file_hash explicitly
				const firstImgUrl = finalPages[0]?.image_url || "";
				const hashMatch = firstImgUrl.match(
					/\/static\/paper_images\/([^/]+)\//,
				);
				const fileHash = hashMatch ? hashMatch[1] : null;

				if (fileHash) formData.append("file_hash", fileHash);

				const response = await fetch(`${API_URL}/api/analyze-layout-lazy`, {
					method: "POST",
					headers,
					body: formData,
				});

				if (!response.ok) {
					const errorText = await response.text();
					log.error("trigger_lazy_layout_analysis", "Analysis failed", {
						pages: batchPages,
						status: response.status,
						error: errorText,
					});
					continue; // Try next batch even if this one failed
				}

				const result = await response.json();

				// 1. Merge detected figures into page state
				if (result.figures && result.figures.length > 0) {
					setPages((prevPages) => {
						const nextPages = prevPages.map((page) => {
							const pageFigures = result.figures.filter(
								(f: any) => f.page_num === page.page_num,
							);
							if (pageFigures.length > 0) {
								const processedFigures = pageFigures.map((f: any) => ({
									...f,
									image_url:
										f.image_url &&
										!f.image_url.startsWith("http") &&
										!f.image_url.startsWith("blob:")
											? `${API_URL}${f.image_url}`
											: f.image_url,
								}));

								// Deduplicate based on BBox or Image URL
								const existingUrls = new Set(
									(page.figures || []).map((ef) => ef.image_url),
								);
								const newUniqueFigures = processedFigures.filter(
									(nf: any) => !existingUrls.has(nf.image_url),
								);

								if (newUniqueFigures.length === 0) return page;

								return {
									...page,
									figures: [...(page.figures || []), ...newUniqueFigures],
								};
							}
							return page;
						});

						// 2. Persist to IndexedDB cache (Crucial for Transient sessions)
						if (paperId && isDbAvailable()) {
							const layoutJson = JSON.stringify(
								nextPages.map((p) => ({
									width: p.width,
									height: p.height,
									words: p.words,
									figures: p.figures,
									links: p.links,
								})),
							);

							getCachedPaper(paperId).then((cached) => {
								savePaperToCache({
									...(cached || {
										id: paperId,
										file_hash: fileHash || "",
										title: "Untitled",
										last_accessed: Date.now(),
									}),
									layout_json: layoutJson,
									last_accessed: Date.now(),
								});
							});
						}

						return nextPages;
					});
				}
			}
			log.info(
				"trigger_lazy_layout_analysis",
				"Completed lazy layout analysis",
			);
		} catch (err) {
			log.error("trigger_lazy_layout_analysis", "Lazy layout analysis error", {
				error: err instanceof Error ? err.message : String(err),
			});
			// Don't re-throw - this is a background enhancement, not critical
		}
	};

	/* TODO (suspended): fetchStamps removed - stamp mode suspended.
	const fetchStamps = async (id: string) => {
		try {
			const headers: HeadersInit = {};
			if (token) headers.Authorization = `Bearer ${token}`;

			const res = await fetch(`${API_URL}/api/stamps/paper/${id}`, { headers });
			if (res.ok) {
				const data = await res.json();
				setStamps(data.stamps);
			}
		} catch (e) {
			log.error("fetch_stamps", "Failed to fetch stamps", { error: e });
		}
	};

	*/

	// Scroll to jump target when it changes
	useEffect(() => {
		if (jumpTarget) {
			const pageId =
				mode === "plaintext"
					? `text-page-${jumpTarget.page}`
					: `page-${jumpTarget.page}`;
			const pageEl = document.getElementById(pageId);
			if (pageEl) {
				// Find scrollable container (assuming one of the parents is overflow-y-auto)
				// In App.tsx it's the div with ".overflow-y-auto"
				const scroller = pageEl.closest(".overflow-y-auto");

				if (scroller) {
					const pageRect = pageEl.getBoundingClientRect();
					const scrollerRect = scroller.getBoundingClientRect();

					// Current scroll position
					const currentScrollTop = scroller.scrollTop;

					// pageRect.top is relative to viewport
					// We need offset from scroller top
					// scrollerRect.top is viewport top of scroller

					// Page top position inside the scrollable content
					const pageTopInScroller =
						currentScrollTop + (pageRect.top - scrollerRect.top);

					// Target Y within the page (height * percentage)
					const targetYInPage = pageRect.height * (jumpTarget.y || 0); // Default to top if y is missing

					// Center the target in the viewport (scroller height / 2)
					const targetScrollTop =
						pageTopInScroller + targetYInPage - scrollerRect.height / 2;

					scroller.scrollTo({
						top: targetScrollTop,
						behavior: "smooth",
					});

					// Also highlight the target location temporarily?
				} else {
					// Fallback if no specific scroller found (e.g. window scroll)
					pageEl.scrollIntoView({ behavior: "smooth", block: "center" });
				}
			}
		}
	}, [jumpTarget, mode]);

	const startAnalysis = async (file: File) => {
		if (processingFileRef.current === file) return;
		processingFileRef.current = file;

		setStatus("uploading");
		setPages([]);
		setLoadedPaperId(null);
		// setStamps([]);

		const formData = new FormData();
		formData.append("file", file);
		formData.append("lang", i18n.language);

		formData.append("mode", "json");
		if (sessionId) {
			formData.append("session_id", sessionId);
		}

		try {
			const headers: HeadersInit = {};
			if (token) headers.Authorization = `Bearer ${token}`;

			const response = await fetch(`${API_URL}/api/analyze-pdf-json`, {
				method: "POST",
				headers,
				body: formData,
			});

			if (!response.ok) {
				const errorData = await response.json().catch(() => ({}));
				throw new Error(errorData.error || "Upload failed");
			}

			const data = await response.json();
			const { task_id, stream_url } = data;
			activeTaskIdRef.current = task_id;

			// Start streaming with retry logic
			await startStreaming(stream_url, 0);
		} catch (err: any) {
			setStatus("error");
			setErrorMsg(err.message);
			processingFileRef.current = null;
			activeTaskIdRef.current = null;
		}
	};

	const startStreaming = async (stream_url: string, retryCount: number = 0) => {
		const maxRetries = 3;
		const retryDelay = 1000 * 2 ** retryCount; // Exponential backoff

		// Close existing if any
		if (eventSourceRef.current) {
			eventSourceRef.current.close();
		}

		setStatus("processing");
		const fullStreamUrl = stream_url.startsWith("http")
			? stream_url
			: `${API_URL}${stream_url}`;
		const es = new EventSource(fullStreamUrl);
		eventSourceRef.current = es;

		es.onmessage = (event) => {
			try {
				const eventData = JSON.parse(event.data);

				if (eventData.type === "page") {
					setPages((prev) => {
						let newData = eventData.data;
						if (!newData || typeof newData.page_num === "undefined") {
							log.warn("sse_message", "Received malformed page data", {
								newData,
							});
							return prev;
						}

						// Prepend API_URL to image_url if it's a relative path
						if (
							newData.image_url &&
							!newData.image_url.startsWith("http") &&
							!newData.image_url.startsWith("blob:")
						) {
							newData = {
								...newData,
								image_url: `${API_URL}${newData.image_url}`,
							};
						}

						// Also prepend to figures if they exist
						if (newData.figures && newData.figures.length > 0) {
							newData = {
								...newData,
								figures: newData.figures.map((f: any) => ({
									...f,
									image_url:
										f.image_url &&
										!f.image_url.startsWith("http") &&
										!f.image_url.startsWith("blob:")
											? `${API_URL}${f.image_url}`
											: f.image_url,
								})),
							};
						}

						const index = prev.findIndex(
							(p) => p.page_num === newData.page_num,
						);
						if (index !== -1) {
							// Merge existing page data (update)
							const newPages = [...prev];
							newPages[index] = { ...newPages[index], ...newData };
							return newPages;
						}
						// Append new page
						return [...prev, newData];
					});
				} else if (eventData.type === "done") {
					setStatus("done");
					if (eventData.paper_id) {
						const pId = eventData.paper_id;
						setLoadedPaperId(pId);

						// Use ref to get the latest pages collected during streaming
						const finalPages = pagesRef.current || [];

						(async () => {
							const imageUrls = finalPages.map((p) => p.image_url);
							// Store as JSON array to avoid collision with Markdown horizontal rules (\n\n---\n\n)
							const ocrText = JSON.stringify(
								finalPages.map((p) => p.content || ""),
							);
							const layoutData = finalPages.map((p) => ({
								width: p.width,
								height: p.height,
								words: p.words,
								figures: p.figures,
								links: p.links,
							}));

							// Extract file_hash from image_url (e.g. /static/paper_images/{hash}/page_1.png)
							let fileHash = "";
							if (imageUrls.length > 0) {
								const match = imageUrls[0].match(
									/\/static\/paper_images\/([^/]+)\//,
								);
								if (match) fileHash = match[1];
							}

							await savePaperToCache({
								id: pId,
								file_hash: fileHash,
								title: processingFileRef.current?.name || "Untitled",
								ocr_text: ocrText,
								layout_json: JSON.stringify(layoutData),
								last_accessed: Date.now(),
							});
							// We don't block on image caching
							cachePaperImages(pId, imageUrls).catch((err) =>
								log.warn("image_cache", "Image caching failed", {
									error: err,
								}),
							);
						})();

						// Trigger lazy layout analysis in background (non-blocking)
						triggerLazyLayoutAnalysis(pId).catch((err) =>
							log.warn("trigger_lazy_layout_analysis", "Lazy analysis failed", {
								error: err,
							}),
						);
					}
					es.close();
					processingFileRef.current = null;
					activeTaskIdRef.current = null;
				} else if (eventData.type === "coordinates_ready") {
					// No action needed; mode is preserved
				} else if (eventData.type === "assist_mode_ready") {
					// No action needed; reserved for future use
				} else if (eventData.type === "error") {
					setStatus("error");
					setErrorMsg(eventData.message);
					es.close();
					processingFileRef.current = null;
					activeTaskIdRef.current = null;
				}
			} catch (_e) {
				// Ignore parsing errors
			}
		};

		es.onerror = (err) => {
			log.error("sse_error", "SSE Error", {
				error: err,
				pagesReceived: pagesRef.current.length,
				retryCount,
				streamUrl: stream_url,
			});

			es.close();

			// If we have pages, consider it partial success
			if (pagesRef.current.length > 0) {
				setStatus("done");
				processingFileRef.current = null;
				activeTaskIdRef.current = null;
				return;
			}

			// Retry logic for connection failures
			if (retryCount < maxRetries) {
				setTimeout(() => {
					startStreaming(stream_url, retryCount + 1);
				}, retryDelay);
			} else {
				setStatus("error");
				setErrorMsg(
					`ネットワークエラーが発生しました。接続を確認して再度お試しください。(URL: ${stream_url})`,
				);
				processingFileRef.current = null;
				activeTaskIdRef.current = null;
			}
		};
	};

	const handleWordClick = useCallback(
		(
			word: string,
			context?: string,
			coords?: { page: number; x: number; y: number },
		) => {
			if (onWordClick) {
				onWordClick(word, context, coords);
			}
		},
		[onWordClick],
	);

	const handleTextSelect = useCallback(
		(text: string, coords: { page: number; x: number; y: number }) => {
			if (onTextSelect) {
				onTextSelect(text, coords);
			}
		},
		[onTextSelect],
	);

	/* TODO (suspended): handleAreaSelect removed - area/crop mode suspended.
	const handleAreaSelect = useCallback(
		async (coords: {
			page: number;
			x: number;
			y: number;
			width: number;
			height: number;
		}) => {
			// Find page data
			const page = pages.find((p) => p.page_num === coords.page);
			if (!page || !onAreaSelect) return;

			try {
				// IndexedDB キャッシュがあればそれを使い、CORS 問題を回避する
				const cachedImage = await db.images.get(page.image_url);
				let blobUrl: string | null = null;
				let imageUrl = page.image_url;
				if (cachedImage?.blob) {
					blobUrl = URL.createObjectURL(cachedImage.blob);
					imageUrl = blobUrl;
				}

				// Load image for cropping
				const img = new Image();
				if (!blobUrl) img.crossOrigin = "anonymous";
				img.src = imageUrl;
				await new Promise((resolve, reject) => {
					img.onload = resolve;
					img.onerror = reject;
				});

				const canvas = document.createElement("canvas");
				// Coords are in relative [0-1] format
				const cropX = coords.x * img.naturalWidth;
				const cropY = coords.y * img.naturalHeight;
				const cropW = coords.width * img.naturalWidth;
				const cropH = coords.height * img.naturalHeight;

				canvas.width = cropW;
				canvas.height = cropH;

				const ctx = canvas.getContext("2d");
				if (!ctx) {
					if (blobUrl) URL.revokeObjectURL(blobUrl);
					return;
				}

				ctx.drawImage(img, cropX, cropY, cropW, cropH, 0, 0, cropW, cropH);
				// drawImage 完了後に BlobURL を解放
				if (blobUrl) URL.revokeObjectURL(blobUrl);

				// Upload the cropped image
				canvas.toBlob(async (blob) => {
					if (!blob) return;
					const formData = new FormData();
					formData.append("file", blob, "crop.png");

					// We need token if auth is enabled
					const headers: HeadersInit = {};
					if (token) headers.Authorization = `Bearer ${token}`;

					const res = await fetch(`${API_URL}/api/upload/image`, {
						method: "POST",
						headers,
						body: formData,
					});

					if (res.ok) {
						const data = await res.json();
						onAreaSelect(data.url, {
							page: coords.page,
							x: coords.x,
							y: coords.y,
						});
						// Switch back to text mode after selection?
						setMode("text");
					}
				} catch (e) {
					log.error("crop_and_upload", "Failed to crop/upload image", {
						error: e,
					});
				}
			}, "image/png");
		},

		[pages, onAreaSelect, token],
	);
	*/

	/* TODO (suspended): handleAddStamp removed - stamp mode suspended.
	const handleAddStamp = useCallback(
		async (page: number, x: number, y: number) => {
			if (!loadedPaperId) {
				alert("Paper ID not found. Please wait for analysis to complete.");
				return;
			}

			const newStamp: Stamp = {
				id: `temp-${Date.now()}`,
				type: selectedStamp,
				x,
				y,
				page_number: page,
			};

			// Optimistic update
			setStamps((prev) => [...prev, newStamp]);

			try {
				const headers: HeadersInit = { "Content-Type": "application/json" };
				if (token) headers.Authorization = `Bearer ${token}`;

				const res = await fetch(
					`${API_URL}/api/stamps/paper/${loadedPaperId}`,
					{
						method: "POST",
						headers,
						body: JSON.stringify({
							stamp_type: selectedStamp,
							x,
							y,
							page_number: page,
						}),
					},
				);

				if (res.ok) {
					const data = await res.json();
					// Update ID from backend
					setStamps((prev) =>
						prev.map((s) =>
							s.id === newStamp.id ? { ...s, id: data.stamp_id } : s,
						),
					);
				} else {
					log.error("add_stamp", "Failed to save stamp");
					// Rollback?
					setStamps((prev) => prev.filter((s) => s.id !== newStamp.id));
				}

			} catch (e) {
				log.error("add_stamp", "Error saving stamp", { error: e });
				// Rollback on network error as well
				setStamps((prev) => prev.filter((s) => s.id !== newStamp.id));
			}

		},
		[loadedPaperId, selectedStamp, token],
	);
	*/

	/* TODO (suspended): handleDeleteStamp removed - stamp mode suspended.
	const handleDeleteStamp = useCallback(
		async (stampId: string) => {
			// Optimistic update
			setStamps((prev) => prev.filter((s) => s.id !== stampId));
			try {
				const headers: HeadersInit = {};
				if (token) headers.Authorization = `Bearer ${token}`;
				await fetch(`${API_URL}/api/stamps/paper/${stampId}`, {
					method: "DELETE",
					headers,
				});
			} catch (e) {
				log.error("delete_stamp", "Failed to delete stamp", { error: e });
				// fetchStamps will reconcile state on next load
			}

		},
		[token],
	);
	*/

	const pagesWithLines: PageWithLines[] = useMemo(
		() => groupWordsIntoLines(pages),
		[pages],
	);

	const loadExistingPaper = async (id: string) => {
		setStatus("processing");
		setLoadedPaperId(id);
		// setStamps([]);

		try {
			// 0. Check IndexedDB Cache First (Offline First / Fast Load)
			// Guests also benefit from IndexedDB cache (CORS avoidance, fast reload within session)
			{
				const cached = await getCachedPaper(id);
				if (cached?.layout_json && cached.file_hash) {
					try {
						const layoutList = JSON.parse(cached.layout_json);
						// Support both new JSON array format and legacy \n\n---\n\n separator
						let ocrParts: string[];
						try {
							const parsed = JSON.parse(cached.ocr_text || "[]");
							ocrParts = Array.isArray(parsed)
								? parsed
								: (cached.ocr_text || "").split("\n\n---\n\n");
						} catch {
							ocrParts = (cached.ocr_text || "").split("\n\n---\n\n");
						}
						const fileHash = cached.file_hash;

						const cachedPages: PageData[] = layoutList.map(
							(layout: any, i: number) => ({
								page_num: i + 1,
								image_url: `${API_URL}/static/paper_images/${fileHash}/page_${i + 1}.png`,
								width: layout?.width || 0,
								height: layout?.height || 0,
								words: layout?.words || [],
								figures: layout?.figures || [],
								links: layout?.links || [],
								content: ocrParts[i] || "",
							}),
						);

						if (cachedPages.length > 0) {
							setPages(cachedPages);
							setStatus("done");
							// Cached papers: preserved current mode

							// Trigger lazy layout analysis to fetch figures if not already present
							const hasFigures = cachedPages.some(
								(p) => p.figures && p.figures.length > 0,
							);
							if (!hasFigures) {
								triggerLazyLayoutAnalysis(id, cachedPages).catch((err) =>
									log.warn(
										"trigger_lazy_layout_analysis",
										"Lazy layout analysis failed",
										{ error: err },
									),
								);
							}

							// Optional: Background check with server to ensure consistency.
							return;
						}
					} catch (e) {
						log.warn(
							"load_existing_paper",
							"Corrupted cache detected, deleting",
							{ error: e },
						);
						await deleteCorruptedCache(id);
					}
				}
			}

			const headers: HeadersInit = {};
			if (token) headers.Authorization = `Bearer ${token}`;

			// 1. Try to fetch full paper data directly first (Fast Load)
			const paperRes = await fetch(`${API_URL}/api/papers/${id}`, { headers });
			if (paperRes.ok) {
				const paperData = await paperRes.json();

				// Save/Update cache with latest metadata if not guest
				if (!isGuest) {
					await savePaperToCache({
						id: id,
						file_hash: paperData.file_hash || "",
						title: paperData.title || paperData.filename,
						ocr_text: paperData.ocr_text,
						layout_json: paperData.layout_json,
						full_summary: paperData.full_summary,
						section_summary_json: paperData.section_summary_json,
						last_accessed: Date.now(),
					});
				}

				if (paperData.layout_json && paperData.file_hash) {
					try {
						const layoutList = JSON.parse(paperData.layout_json);
						const ocrParts = (paperData.ocr_text || "").split("\n\n---\n\n");
						const fileHash = paperData.file_hash;

						const fullPages: PageData[] = layoutList.map(
							(layout: any, i: number) => ({
								page_num: i + 1,
								image_url: `${API_URL}/static/paper_images/${fileHash}/page_${i + 1}.png`,
								width: layout?.width || 0,
								height: layout?.height || 0,
								words: layout?.words || [],
								figures: layout?.figures || [],
								links: layout?.links || [],
								content: ocrParts[i] || "",
							}),
						);

						if (fullPages.length > 0) {
							setPages(fullPages);
							setStatus("done");
							// Full paper data has coordinates ready

							// Cache images in background for all users (CORS avoidance, fast reload)
							cachePaperImages(
								id,
								fullPages.map((p) => p.image_url),
							).catch((err) =>
								log.warn("image_cache", "Image caching failed", { error: err }),
							);

							// Trigger lazy layout analysis to fetch figures if not already present
							const hasFigures = fullPages.some(
								(p) => p.figures && p.figures.length > 0,
							);
							if (!hasFigures) {
								triggerLazyLayoutAnalysis(id, fullPages).catch((err) =>
									log.warn(
										"trigger_lazy_layout_analysis",
										"Lazy analysis failed",
										{ error: err },
									),
								);
							}

							return; // Success! No need to stream.
						}
					} catch (parseErr) {
						log.warn(
							"load_existing_paper",
							"Failed to parse cached layout, falling back to stream",
							{ error: parseErr },
						);
					}
				}
			}

			// 2. Fallback to streaming if not already processed/cached in a way we can use
			// If we are already displaying some pages, don't clear them until we get the first chunk from the new stream
			// to avoid a white flicker.
			// setPages([]); // Removed immediate clear
			const formData = new FormData();
			if (sessionId) formData.append("session_id", sessionId);

			const response = await fetch(`${API_URL}/api/analyze-paper/${id}`, {
				method: "POST",
				headers,
				body: formData,
			});

			if (!response.ok) throw new Error("Failed to load paper");

			const data = await response.json();
			const { stream_url } = data;

			const fullStreamUrl = stream_url.startsWith("http")
				? stream_url
				: `${API_URL}${stream_url}`;
			const es = new EventSource(fullStreamUrl);
			eventSourceRef.current = es;

			es.onmessage = (event) => {
				try {
					const eventData = JSON.parse(event.data);
					if (eventData.type === "page") {
						setPages((prev) => {
							const newData = eventData.data;
							const index = prev.findIndex(
								(p) => p.page_num === newData.page_num,
							);
							if (index !== -1) {
								const newPages = [...prev];
								newPages[index] = { ...newPages[index], ...newData };
								return newPages;
							}
							return [...prev, newData];
						});
					} else if (eventData.type === "done") {
						setStatus("done");
						es.close();
					} else if (eventData.type === "error") {
						setStatus("error");
						setErrorMsg(eventData.message);
						es.close();
					}
				} catch (_e) {
					// Ignore JSON parse errors for incomplete chunks
				}
			};

			es.onerror = (err) => {
				log.error("sse_error", "SSE Error during reload", { error: err });
				es.close();
				if (pages.length === 0) setStatus("error"); // Only error if we got nothing
			};
		} catch (err: any) {
			setStatus("error");
			setErrorMsg(err.message);
		}
	};

	return (
		<div className="w-full max-w-5xl mx-auto p-2 md:p-4 relative min-h-full pb-20">
			{/* Non-blocking status indicators */}
			{(status === "uploading" || status === "processing") && (
				<div className="fixed bottom-4 right-4 z-50 bg-white rounded-full shadow-lg p-3 border border-orange-200">
					<div className="flex items-center gap-2">
						<div className="animate-spin rounded-full h-4 w-4 border-2 border-orange-200 border-t-orange-600"></div>
						<span className="text-xs text-orange-600 font-medium">
							{status === "uploading"
								? t("viewer.uploading_pdf")
								: "読み込み中..."}
						</span>
					</div>
				</div>
			)}

			{/* Initial state - no PDF loaded */}
			{status === "idle" &&
				!uploadFile &&
				!propPaperId &&
				pages.length === 0 && (
					<div className="text-center p-10 text-gray-400 border-2 border-dashed border-gray-200 rounded-xl">
						{t("viewer.waiting_pdf")}
					</div>
				)}

			{/* Processing with no pages yet - show friendly message */}
			{(status === "uploading" || status === "processing") &&
				pages.length === 0 && (
					<div className="text-center p-10 text-gray-400">
						<div className="text-4xl mb-4">📄</div>
						<p className="text-sm">
							{status === "uploading"
								? "PDFをアップロード中..."
								: "PDFを処理中..."}
						</p>
						<p className="text-xs mt-2 text-gray-300">
							このまま他の操作を続けることができます
						</p>
					</div>
				)}

			{status === "error" && (
				<div className="bg-red-50 text-red-600 p-4 rounded-lg mb-4">
					Error: {errorMsg}
				</div>
			)}

			{/* Content Area - Show as soon as we have pages */}
			{pages.length > 0 && (
				<>
					{/* Content Area */}
					{/* TextMode: 初期状態からマウント。CSS display で高速切り替え */}
					<div className={mode === "plaintext" ? "block" : "hidden"}>
						<TextModeViewer
							pages={pagesWithLines}
							onWordClick={handleWordClick}
							onTextSelect={handleTextSelect}
							onAskAI={onAskAI}
							searchTerm={searchTerm}
						/>
					</div>

					{/* PDF グリッド: 初回アクセス時に初めてマウント（遅延マウント）。
					     以降は CSS display トグルで再マウントコストなしに切り替え */}
					{hasMountedPdfMode && (
						<div className={mode !== "plaintext" ? "block" : "hidden"}>
							{/* group/viewer + data-click-mode で CSS バリアント (group-data-[click-mode]/viewer:*)
							    を制御。isClickMode を prop として渡さないことで、モード切り替え時に
							    全 PDFPage が再レンダーされるのを防ぐ。 */}
							<div
								className="space-y-6 group/viewer"
								data-click-mode={mode === "text" ? "" : undefined}
							>
								{/* TODO: Stamp/Area mode suspended. Restore PDFPage props to re-enable:
								     stamps={stamps} isStampMode={mode === "stamp"} onAddStamp={handleAddStamp}
								     onDeleteStamp={handleDeleteStamp} isAreaMode={mode === "area"} onAreaSelect={handleAreaSelect} */}
								{pages.map((page) => (
									<PDFPage
										key={page.page_num}
										page={page}
										onWordClick={handleWordClick}
										onTextSelect={handleTextSelect}
										onAskAI={onAskAI}
										onFigureSelect={onFigureSelect}
										jumpTarget={jumpTarget}
										searchTerm={searchTerm}
										currentSearchMatch={currentSearchMatch}
										evidenceHighlights={evidenceHighlights[page.page_num]}
										isDev={isDev}
									/>
								))}
							</div>
						</div>
					)}

					{/* TODO: Stamp Palette suspended along with stamp mode.
					     Restore when stamp mode is re-enabled. */}
					{/* {loadedPaperId && mode === "stamp" && (
						<StampPalette
							isStampMode={true}
							onToggleMode={() => setMode("text")}
							selectedStamp={selectedStamp}
							onSelectStamp={setSelectedStamp}
							token={token ?? undefined}
						/>
					)} */}
				</>
			)}
		</div>
	);
};

export default PDFViewer;

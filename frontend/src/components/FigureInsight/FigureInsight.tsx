import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { API_URL } from "@/config";
import { createLogger } from "@/lib/logger";
import CopyButton from "../Common/CopyButton";
import FeedbackSection from "../Common/FeedbackSection";
import MarkdownContent from "../Common/MarkdownContent";
import type { SelectedFigure } from "../PDF/types";

const log = createLogger("FigureInsight");

interface FigureInsightProps {
	selectedFigure?: SelectedFigure | null;
	sessionId: string;
}

interface FigureResult {
	figure: SelectedFigure;
	explanation: string | null;
	isLoading: boolean;
	error: string | null;
	traceId?: string;
}

// セッション単位のキャッシュ（アンマウントされても状態を保持する）
const globalStackCache: Record<string, FigureResult[]> = {};
const globalAnalyzedIds: Record<string, Set<string>> = {};
const globalRequestingIds: Record<string, Set<string>> = {};

function initSessionCache(sessionId: string) {
	if (!globalStackCache[sessionId]) globalStackCache[sessionId] = [];
	if (!globalAnalyzedIds[sessionId]) globalAnalyzedIds[sessionId] = new Set();
	if (!globalRequestingIds[sessionId])
		globalRequestingIds[sessionId] = new Set();
}

const FigureInsight: React.FC<FigureInsightProps> = ({
	selectedFigure,
	sessionId,
}) => {
	initSessionCache(sessionId);

	// スタックされた解析済み図表の配列（新しいものが先頭）
	const [stackState, setStackState] = useState<FigureResult[]>(
		globalStackCache[sessionId],
	);
	const [zoomedImage, setZoomedImage] = useState<string | null>(null);

	// セッションが変更されたときに状態を復元
	useEffect(() => {
		initSessionCache(sessionId);
		setStackState(globalStackCache[sessionId]);
	}, [sessionId]);

	// キャッシュとローカルステートを同期更新するラッパー関数
	const setStack = (updater: React.SetStateAction<FigureResult[]>) => {
		setStackState((prev) => {
			const next = typeof updater === "function" ? updater(prev) : updater;
			globalStackCache[sessionId] = next;
			return next;
		});
	};

	/**
	 * selectedFigure が変化したとき、まだ解析していない図であれば
	 * スタックに追加してAPIを呼び出す。
	 * 既に解析済みの場合はAPIを呼ばない。
	 */
	useEffect(() => {
		if (!selectedFigure) return;

		const figureId =
			selectedFigure.id ||
			(selectedFigure.image_url
				? `transient-${selectedFigure.image_url}`
				: null);
		if (!figureId) return;

		// 既に解析済み or 現在リクエスト中の場合はスキップ
		if (
			globalAnalyzedIds[sessionId].has(figureId) ||
			globalRequestingIds[sessionId].has(figureId)
		) {
			return;
		}

		// スタックに「ローディング中」の要素を追加
		const newEntry: FigureResult = {
			figure: selectedFigure,
			explanation: null,
			isLoading: true,
			error: null,
		};

		setStack((prev) => {
			// 同じ figureId が既にスタックにある場合は重複追加しない
			if (prev.some((r) => getFigureId(r.figure) === figureId)) {
				return prev;
			}
			return [newEntry, ...prev];
		});

		globalRequestingIds[sessionId].add(figureId);

		const idForApi = selectedFigure.id || "transient";
		fetch(`${API_URL}/api/figures/${idForApi}/explain`, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ image_url: selectedFigure?.image_url }),
		})
			.then(async (res) => {
				if (res.ok) return res.json();
				const errorBody = await res.json().catch(() => ({}));
				const detail =
					errorBody.detail || errorBody.error || `HTTP ${res.status}`;
				log.error("handle_explain", "API error", {
					figureId,
					status: res.status,
					detail,
				});
				setStack((prev) =>
					prev.map((r) =>
						getFigureId(r.figure) === figureId
							? {
									...r,
									isLoading: false,
									error: `図の解析に失敗しました (${detail})`,
								}
							: r,
					),
				);
				return null;
			})
			.then((data) => {
				if (data) {
					setStack((prev) =>
						prev.map((r) =>
							getFigureId(r.figure) === figureId
								? {
										...r,
										isLoading: false,
										explanation: data.explanation ?? null,
										traceId: data.trace_id,
									}
								: r,
						),
					);
					globalAnalyzedIds[sessionId].add(figureId);
				}
			})
			.catch((e) => {
				log.error("handle_explain", "Failed to explain figure", {
					figureId,
					error: e,
				});
				setStack((prev) =>
					prev.map((r) =>
						getFigureId(r.figure) === figureId
							? {
									...r,
									isLoading: false,
									error: "図の解析に失敗しました (ネットワークエラー)",
								}
							: r,
					),
				);
			})
			.finally(() => {
				globalRequestingIds[sessionId].delete(figureId);
			});
	}, [selectedFigure?.id, selectedFigure?.image_url, sessionId]); // selectedFigure, sessionId が変わったときだけ発動

	if (!selectedFigure && stackState.length === 0) {
		return (
			<div className="text-center py-16 px-6">
				<div className="w-16 h-16 bg-white rounded-2xl shadow-sm flex items-center justify-center mx-auto mb-4 border border-slate-100">
					<svg
						className="w-8 h-8 text-slate-300"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
					>
						<path
							strokeLinecap="round"
							strokeLinejoin="round"
							strokeWidth="1.5"
							d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
						/>
					</svg>
				</div>
				<h4 className="text-xs font-bold text-slate-500 mb-1">
					図をクリックして解説
				</h4>
				<p className="text-[10px] text-slate-400 leading-relaxed">
					クリックモードで論文中の図・表をクリックすると、ここに表示されます。
				</p>
			</div>
		);
	}

	return (
		<div className="relative space-y-4">
			{stackState.length > 1 && (
				<div className="flex items-center justify-between mb-1">
					<span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
						{stackState.length}件の図解
					</span>
					<button
						type="button"
						onClick={() => {
							setStack([]);
							globalAnalyzedIds[sessionId].clear();
						}}
						className="text-[10px] text-slate-400 hover:text-rose-500 transition-colors font-bold uppercase tracking-wider"
					>
						すべてクリア
					</button>
				</div>
			)}

			{stackState.map((result, idx) => (
				<FigureCard
					key={getFigureId(result.figure) || idx}
					result={result}
					isLatest={idx === 0}
					sessionId={sessionId}
					onZoom={(url) => setZoomedImage(url)}
				/>
			))}

			{/* Zoom Modal */}
			{zoomedImage &&
				createPortal(
					<div className="fixed inset-0 z-[100] flex items-center justify-center p-4 md:p-8 overflow-hidden animate-fade-in">
						<button
							type="button"
							className="absolute inset-0 w-full h-full bg-black/80 cursor-pointer border-none"
							onClick={() => setZoomedImage(null)}
							aria-label="Close zoom backdrop"
						/>
						<button
							type="button"
							className="absolute top-6 right-6 text-white/70 hover:text-white p-2 hover:bg-white/10 rounded-full transition-all z-[110]"
							onClick={() => setZoomedImage(null)}
							aria-label="Close zoom"
						>
							<svg
								className="w-8 h-8"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
							>
								<path
									strokeLinecap="round"
									strokeLinejoin="round"
									strokeWidth="2"
									d="M6 18L18 6M6 6l12 12"
								/>
							</svg>
						</button>
						<div
							role="dialog"
							aria-modal="true"
							className="relative max-w-5xl w-full max-h-full flex items-center justify-center pointer-events-none"
						>
							<img
								src={zoomedImage}
								alt="Zoomed figure"
								className="max-w-full max-h-[90vh] object-contain shadow-2xl rounded-lg pointer-events-auto cursor-default"
							/>
						</div>
					</div>,
					document.body,
				)}
		</div>
	);
};

// ------- Helper -------

function getFigureId(figure: SelectedFigure): string {
	return figure.id || `transient-${figure.image_url}`;
}

interface FigureCardProps {
	result: FigureResult;
	isLatest: boolean;
	sessionId: string;
	onZoom: (url: string) => void;
}

const FigureCard: React.FC<FigureCardProps> = ({
	result,
	isLatest,
	sessionId,
	onZoom,
}) => {
	const { figure, explanation, isLoading, error, traceId } = result;
	const [collapsed, setCollapsed] = useState(!isLatest);

	return (
		<div
			className={`bg-white rounded-xl shadow-sm border overflow-hidden transition-all ${
				isLatest ? "border-orange-200 shadow-orange-100/50" : "border-slate-200"
			}`}
		>
			{/* 画像エリア */}
			<button
				type="button"
				onClick={() => {
					if (!figure.image_url) return;
					const fullUrl = figure.image_url.startsWith("http")
						? figure.image_url
						: `${API_URL}${figure.image_url}`;
					onZoom(fullUrl);
				}}
				className="relative w-full bg-slate-100 aspect-video flex items-center justify-center overflow-hidden border-b border-slate-100 cursor-zoom-in group/img border-none p-0"
			>
				<img
					src={
						figure.image_url.startsWith("http")
							? figure.image_url
							: `${API_URL}${figure.image_url}`
					}
					alt={`Figure on page ${figure.page_number}`}
					className="max-w-full max-h-full object-contain transition-transform group-hover/img:scale-105"
				/>
				<div className="absolute inset-0 bg-black/0 group-hover/img:bg-black/5 transition-colors flex items-center justify-center">
					<div className="opacity-0 group-hover/img:opacity-100 transition-opacity bg-white/90 p-2 rounded-full shadow-lg text-orange-600">
						<svg
							className="w-5 h-5"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
						>
							<path
								strokeLinecap="round"
								strokeLinejoin="round"
								strokeWidth="2"
								d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7"
							/>
						</svg>
					</div>
				</div>
				<div className="absolute top-2 left-2 bg-black/60 text-white text-[10px] font-bold px-2 py-0.5 rounded-full backdrop-blur-sm">
					P.{figure.page_number}
				</div>
				{figure.label && figure.label !== "image" && (
					<div className="absolute top-2 right-2 bg-orange-600/80 text-white text-[9px] font-bold px-2 py-0.5 rounded-full backdrop-blur-sm uppercase">
						{figure.label}
					</div>
				)}
			</button>

			{/* キャプション */}
			{figure.caption && (
				<p className="px-4 pt-3 text-[10px] text-slate-500 leading-relaxed border-b border-slate-100 pb-3">
					{figure.caption}
				</p>
			)}

			{/* 解説ヘッダー（折りたたみトグル） */}
			<button
				type="button"
				className="w-full flex items-center justify-between px-4 py-2 bg-slate-50/50 hover:bg-slate-50 transition-colors border-none text-left"
				onClick={() => setCollapsed((c) => !c)}
			>
				<span className="text-[10px] font-bold text-orange-600 uppercase tracking-wider">
					{isLoading ? (
						<span className="flex items-center gap-1.5">
							<span className="w-3 h-3 border-2 border-orange-300 border-t-orange-600 rounded-full animate-spin inline-block" />
							AIが解析中...
						</span>
					) : (
						"Analysis"
					)}
				</span>
				{!isLoading && (
					<svg
						className={`w-4 h-4 text-slate-400 transition-transform ${collapsed ? "" : "rotate-180"}`}
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
					>
						<path
							strokeLinecap="round"
							strokeLinejoin="round"
							strokeWidth="2"
							d="M19 9l-7 7-7-7"
						/>
					</svg>
				)}
			</button>

			{/* 解説エリア（折りたたみ可能） */}
			{!collapsed && (
				<div className="p-4">
					{isLoading ? (
						<div className="flex items-center justify-center gap-2 py-4 text-orange-600">
							<div className="w-3.5 h-3.5 border-2 border-orange-300 border-t-orange-600 rounded-full animate-spin" />
							<span className="text-[11px] font-bold">AIが解析中...</span>
						</div>
					) : error ? (
						<p className="text-center text-[10px] text-rose-500 py-2">
							{error}
						</p>
					) : explanation ? (
						<>
							<div className="flex justify-end mb-1">
								<CopyButton text={explanation} size={12} traceId={traceId} />
							</div>
							<MarkdownContent className="prose prose-xs max-w-none text-xs text-slate-600 leading-relaxed">
								{explanation}
							</MarkdownContent>

							{/* フィードバック */}
							<FeedbackSection
								sessionId={sessionId}
								targetType="figure_insight"
								targetId={getFigureId(figure)}
								traceId={traceId}
							/>
						</>
					) : (
						<p className="text-center text-[10px] text-slate-400 py-2">
							解析結果はありません
						</p>
					)}
				</div>
			)}
		</div>
	);
};

export default FigureInsight;

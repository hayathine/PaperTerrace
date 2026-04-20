import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { useBookmarks } from "@/db/hooks";
import type { Bookmark } from "@/db/index";
import {
	deletePaper,
	fetchUserPapers,
	fetchUserStats,
	fetchUserTranslations,
	type PaperEntry,
	type TranslationEntry,
	type UserStats,
} from "@/lib/dashboard";
import { createLogger } from "@/lib/logger";

const log = createLogger("Dashboard");

const TRANSLATIONS_PER_PAGE = 20;

function StatCard({
	label,
	value,
	icon,
}: {
	label: string;
	value: number;
	icon: React.ReactNode;
}) {
	return (
		<div className="bg-white rounded-2xl p-5 shadow-sm border border-slate-200 flex flex-col items-center gap-2 min-w-[130px]">
			<div className="w-10 h-10 rounded-xl bg-orange-50 flex items-center justify-center text-orange-600">
				{icon}
			</div>
			<span className="text-2xl font-bold text-slate-800">{value}</span>
			<span className="text-xs font-semibold text-slate-400 uppercase tracking-wider text-center">
				{label}
			</span>
		</div>
	);
}

export default function Dashboard() {
	const { user, token } = useAuth();
	const navigate = useNavigate();

	const { getBookmarks, deleteBookmark } = useBookmarks();
	const [stats, setStats] = useState<UserStats | null>(null);
	const [papers, setPapers] = useState<PaperEntry[]>([]);
	const [bookmarks, setBookmarks] = useState<Bookmark[]>([]);
	const [paperSearch, setPaperSearch] = useState("");
	const [translations, setTranslations] = useState<TranslationEntry[]>([]);
	const [totalTranslations, setTotalTranslations] = useState(0);
	const [page, setPage] = useState(1);
	const [loading, setLoading] = useState(() => !!token);
	const [papersLoading, setPapersLoading] = useState(() => !!token);
	const [translationsLoading, setTranslationsLoading] = useState(false);
	const [deletingPaperId, setDeletingPaperId] = useState<string | null>(null);
	const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
	// 初回ロード済みフラグ（token更新による再フェッチでスケルトンを再表示しない）
	const initialLoadDone = useRef(false);

	const filteredPapers = useMemo(() => {
		if (!paperSearch.trim()) return papers;
		const q = paperSearch.toLowerCase();
		return papers.filter(
			(p) =>
				(p.title ?? "").toLowerCase().includes(q) ||
				(Array.isArray(p.tags)
					? (p.tags as string[]).some((t) => t.toLowerCase().includes(q))
					: false),
		);
	}, [papers, paperSearch]);

	useEffect(() => {
		if (!token) return;
		// 初回のみスケルトン表示。token更新（JWT更新）はバックグラウンドで再フェッチ
		const isFirst = !initialLoadDone.current;
		if (isFirst) {
			setLoading(true);
			setPapersLoading(true);
			initialLoadDone.current = true;
		}
		fetchUserStats(token)
			.then(setStats)
			.catch((e) => log.error("fetch_stats", "Failed to fetch stats", { e }))
			.finally(() => setLoading(false));
		fetchUserPapers(token, 100)
			.then((res) => setPapers(res.papers))
			.catch((e) => log.error("fetch_papers", "Failed to fetch papers", { e }))
			.finally(() => setPapersLoading(false));
		getBookmarks().then(setBookmarks);
	}, [token, getBookmarks]);

	useEffect(() => {
		if (!token) return;
		setTranslationsLoading(true);
		fetchUserTranslations(token, page, TRANSLATIONS_PER_PAGE)
			.then((res) => {
				setTranslations(res.translations);
				setTotalTranslations(res.total);
			})
			.catch((e) =>
				log.error("fetch_translations", "Failed to fetch translations", { e }),
			)
			.finally(() => setTranslationsLoading(false));
	}, [token, page]);

	const totalPages = Math.ceil(totalTranslations / TRANSLATIONS_PER_PAGE);

	const avatarUrl = user?.image;
	const displayName = user?.name ?? user?.email ?? "ユーザー";
	const email = user?.email ?? "";
	const createdAt = user?.createdAt
		? new Date(user.createdAt).toLocaleDateString("ja-JP", {
				year: "numeric",
				month: "long",
				day: "numeric",
			})
		: "";

	return (
		<div className="min-h-screen bg-slate-50">
			{/* Header */}
			<header className="bg-white border-b border-slate-100 sticky top-0 z-10">
				<div className="max-w-3xl mx-auto px-4 py-3 flex items-center gap-3">
					<button
						type="button"
						onClick={() => navigate("/")}
						className="p-2 rounded-xl hover:bg-slate-100 text-slate-500 transition-colors"
						aria-label="戻る"
					>
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
								d="M15 19l-7-7 7-7"
							/>
						</svg>
					</button>
					<div className="w-7 h-7 rounded-lg bg-gradient-to-tr from-orange-600 to-amber-500 flex items-center justify-center">
						<svg
							className="w-4 h-4 text-white"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
						>
							<path
								strokeLinecap="round"
								strokeLinejoin="round"
								strokeWidth="2"
								d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
							/>
						</svg>
					</div>
					<span className="font-bold text-slate-700">マイダッシュボード</span>
				</div>
			</header>

			<main className="max-w-3xl mx-auto px-4 py-8 space-y-8">
				{/* Profile */}
				<section className="bg-white rounded-2xl p-6 shadow-sm border border-slate-200 flex items-center gap-5">
					{avatarUrl ? (
						<img
							src={avatarUrl}
							alt={displayName}
							className="w-16 h-16 rounded-2xl object-cover shadow-md"
						/>
					) : (
						<div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-orange-600 to-amber-500 flex items-center justify-center text-white text-2xl font-bold shadow-md shadow-orange-200">
							{displayName.charAt(0).toUpperCase()}
						</div>
					)}
					<div className="flex-1 min-w-0">
						<p className="text-lg font-bold text-slate-800 truncate">
							{displayName}
						</p>
						{email && (
							<p className="text-sm text-slate-400 truncate">{email}</p>
						)}
						{createdAt && (
							<p className="text-xs text-slate-300 mt-1">{createdAt} 登録</p>
						)}
					</div>
				</section>

				{/* Stats */}
				<section>
					<h2 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">
						学習サマリー
					</h2>
					{loading ? (
						<div className="flex gap-3 overflow-x-auto pb-1">
							{[...Array(4)].map((_, i) => (
								<div
									key={i}
									className="bg-white rounded-2xl p-5 shadow-sm border border-slate-200 flex flex-col items-center gap-2 min-w-[130px] animate-pulse"
								>
									<div className="w-10 h-10 rounded-xl bg-slate-100" />
									<div className="w-8 h-6 bg-slate-100 rounded" />
									<div className="w-16 h-3 bg-slate-100 rounded" />
								</div>
							))}
						</div>
					) : (
						<div className="flex gap-3 overflow-x-auto pb-1">
							<StatCard
								label="読んだ論文"
								value={stats?.paper_count ?? 0}
								icon={
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
											d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
										/>
									</svg>
								}
							/>
							<StatCard
								label="ノート"
								value={stats?.note_count ?? 0}
								icon={
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
											d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
										/>
									</svg>
								}
							/>
							<StatCard
								label="翻訳・解説"
								value={stats?.translation_count ?? 0}
								icon={
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
											d="M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129"
										/>
									</svg>
								}
							/>
							<StatCard
								label="チャット"
								value={stats?.chat_count ?? 0}
								icon={
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
											d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
										/>
									</svg>
								}
							/>
						</div>
					)}
				</section>

				{/* Papers History */}
				<section>
					<div className="flex items-center justify-between mb-3">
						<h2 className="text-xs font-bold uppercase tracking-wider text-slate-400">
							読んだ論文
						</h2>
						{papers.length > 0 && (
							<span className="text-xs text-slate-400">{papers.length} 件</span>
						)}
					</div>
					{/* Search bar */}
					{papers.length > 0 && (
						<div className="relative mb-2">
							<svg
								className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400 pointer-events-none"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
							>
								<path
									strokeLinecap="round"
									strokeLinejoin="round"
									strokeWidth="2"
									d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
								/>
							</svg>
							<input
								type="text"
								value={paperSearch}
								onChange={(e) => setPaperSearch(e.target.value)}
								placeholder="タイトル・タグで検索..."
								className="w-full pl-8 pr-4 py-2 text-sm bg-white border border-slate-200 rounded-xl text-slate-700 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-orange-300 focus:border-transparent"
							/>
							{paperSearch && (
								<button
									type="button"
									onClick={() => setPaperSearch("")}
									className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
								>
									<svg
										className="w-3.5 h-3.5"
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
							)}
						</div>
					)}
					<div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
						{papersLoading ? (
							<div className="divide-y divide-slate-100">
								{[...Array(4)].map((_, i) => (
									<div key={i} className="px-5 py-4 animate-pulse flex gap-3">
										<div className="w-8 h-8 rounded-lg bg-slate-100 shrink-0" />
										<div className="flex-1 space-y-2 py-1">
											<div className="w-3/4 h-3.5 bg-slate-100 rounded" />
											<div className="w-1/3 h-2.5 bg-slate-100 rounded" />
										</div>
									</div>
								))}
							</div>
						) : filteredPapers.length === 0 ? (
							<div className="flex flex-col items-center justify-center py-16 text-slate-300">
								<svg
									className="w-12 h-12 mb-3"
									fill="none"
									stroke="currentColor"
									viewBox="0 0 24 24"
								>
									<path
										strokeLinecap="round"
										strokeLinejoin="round"
										strokeWidth="1.5"
										d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
									/>
								</svg>
								<p className="text-sm font-semibold">
									{paperSearch
										? "一致する論文がありません"
										: "論文はまだありません"}
								</p>
								{!paperSearch && (
									<p className="text-xs mt-1">
										PDFをアップロードして読み始めましょう
									</p>
								)}
							</div>
						) : (
							<div className="divide-y divide-slate-100">
								{filteredPapers.map((p) => (
									<div
										key={p.paper_id}
										className="w-full px-5 py-4 hover:bg-orange-50 transition-colors flex items-center gap-3 group"
									>
										<button
											type="button"
											onClick={() => navigate(`/paper/${p.paper_id}`)}
											className="flex items-center gap-3 flex-1 min-w-0 text-left"
										>
											<div className="w-8 h-8 rounded-lg bg-orange-50 group-hover:bg-orange-100 flex items-center justify-center text-orange-500 shrink-0 transition-colors">
												<svg
													className="w-4 h-4"
													fill="none"
													stroke="currentColor"
													viewBox="0 0 24 24"
												>
													<path
														strokeLinecap="round"
														strokeLinejoin="round"
														strokeWidth="2"
														d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
													/>
												</svg>
											</div>
											<div className="flex-1 min-w-0">
												<p className="text-sm font-semibold text-slate-700 truncate group-hover:text-orange-700 transition-colors">
													{p.title ?? "タイトル未設定"}
												</p>
												<div className="flex items-center gap-2 mt-0.5">
													<p className="text-xs text-slate-400">
														{new Date(p.created_at).toLocaleDateString(
															"ja-JP",
															{
																year: "numeric",
																month: "short",
																day: "numeric",
															},
														)}
													</p>
													{Array.isArray(p.tags) && p.tags.length > 0 && (
														<div className="flex gap-1 flex-wrap">
															{(p.tags as string[]).slice(0, 3).map((tag) => (
																<span
																	key={tag}
																	className="text-[10px] bg-orange-50 text-orange-600 px-1.5 py-0.5 rounded-full"
																>
																	{tag}
																</span>
															))}
														</div>
													)}
												</div>
											</div>
											<svg
												className="w-4 h-4 text-slate-300 group-hover:text-orange-400 shrink-0 transition-colors"
												fill="none"
												stroke="currentColor"
												viewBox="0 0 24 24"
											>
												<path
													strokeLinecap="round"
													strokeLinejoin="round"
													strokeWidth="2"
													d="M9 5l7 7-7 7"
												/>
											</svg>
										</button>
										{confirmDeleteId === p.paper_id ? (
											<div className="flex items-center gap-1 shrink-0">
												<button
													type="button"
													onClick={async () => {
														if (!token) return;
														setDeletingPaperId(p.paper_id);
														setConfirmDeleteId(null);
														try {
															await deletePaper(token, p.paper_id);
															setPapers((prev) =>
																prev.filter((x) => x.paper_id !== p.paper_id),
															);
														} catch (e) {
															log.error(
																"delete_paper",
																"Failed to delete paper",
																{ e },
															);
														} finally {
															setDeletingPaperId(null);
														}
													}}
													className="text-[10px] font-semibold px-2 py-1 rounded-lg bg-red-100 text-red-600 hover:bg-red-200 transition-colors"
												>
													削除
												</button>
												<button
													type="button"
													onClick={() => setConfirmDeleteId(null)}
													className="text-[10px] font-semibold px-2 py-1 rounded-lg bg-slate-100 text-slate-500 hover:bg-slate-200 transition-colors"
												>
													戻る
												</button>
											</div>
										) : (
											<button
												type="button"
												onClick={() => setConfirmDeleteId(p.paper_id)}
												disabled={deletingPaperId === p.paper_id}
												className="p-1.5 rounded-lg text-slate-300 hover:text-red-400 hover:bg-red-50 transition-colors shrink-0 opacity-0 group-hover:opacity-100"
												title="論文を削除"
											>
												{deletingPaperId === p.paper_id ? (
													<svg
														className="w-3.5 h-3.5 animate-spin"
														fill="none"
														viewBox="0 0 24 24"
													>
														<circle
															className="opacity-25"
															cx="12"
															cy="12"
															r="10"
															stroke="currentColor"
															strokeWidth="4"
														/>
														<path
															className="opacity-75"
															fill="currentColor"
															d="M4 12a8 8 0 018-8v8H4z"
														/>
													</svg>
												) : (
													<svg
														className="w-3.5 h-3.5"
														fill="none"
														stroke="currentColor"
														viewBox="0 0 24 24"
													>
														<path
															strokeLinecap="round"
															strokeLinejoin="round"
															strokeWidth="2"
															d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
														/>
													</svg>
												)}
											</button>
										)}
									</div>
								))}
							</div>
						)}
					</div>
				</section>

				{/* Bookmarks */}
				{bookmarks.length > 0 && (
					<section>
						<div className="flex items-center justify-between mb-3">
							<h2 className="text-xs font-bold uppercase tracking-wider text-slate-400">
								しおり
							</h2>
							<span className="text-xs text-slate-400">
								{bookmarks.length} 件
							</span>
						</div>
						<div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
							<div className="divide-y divide-slate-100">
								{bookmarks.map((bm) => (
									<div
										key={bm.id}
										className="px-5 py-3 flex items-center gap-3 hover:bg-orange-50 transition-colors group"
									>
										<button
											type="button"
											onClick={() => navigate(`/paper/${bm.paper_id}`)}
											className="flex items-center gap-3 flex-1 min-w-0 text-left"
										>
											<div className="w-7 h-7 rounded-lg bg-amber-50 group-hover:bg-amber-100 flex items-center justify-center text-amber-500 shrink-0 transition-colors">
												<svg
													className="w-3.5 h-3.5"
													fill="currentColor"
													viewBox="0 0 24 24"
												>
													<path d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
												</svg>
											</div>
											<div className="flex-1 min-w-0">
												<p className="text-sm font-semibold text-slate-700 truncate group-hover:text-orange-700 transition-colors">
													{bm.paper_title}
												</p>
												<p className="text-xs text-slate-400 mt-0.5">
													P.{bm.page_number} ·{" "}
													{new Date(bm.created_at).toLocaleDateString("ja-JP", {
														month: "short",
														day: "numeric",
													})}
												</p>
											</div>
										</button>
										<button
											type="button"
											onClick={async () => {
												if (bm.id != null) {
													await deleteBookmark(bm.id);
													setBookmarks((prev) =>
														prev.filter((b) => b.id !== bm.id),
													);
												}
											}}
											className="p-1.5 rounded-lg text-slate-300 hover:text-red-400 hover:bg-red-50 transition-colors shrink-0"
											title="しおりを削除"
										>
											<svg
												className="w-3.5 h-3.5"
												fill="none"
												stroke="currentColor"
												viewBox="0 0 24 24"
											>
												<path
													strokeLinecap="round"
													strokeLinejoin="round"
													strokeWidth="2"
													d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
												/>
											</svg>
										</button>
									</div>
								))}
							</div>
						</div>
					</section>
				)}

				{/* Translation History */}
				<section>
					<div className="flex items-center justify-between mb-3">
						<h2 className="text-xs font-bold uppercase tracking-wider text-slate-400">
							翻訳・解説履歴
						</h2>
						{totalTranslations > 0 && (
							<span className="text-xs text-slate-400">
								全 {totalTranslations} 件
							</span>
						)}
					</div>

					<div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
						{translationsLoading ? (
							<div className="divide-y divide-slate-100">
								{[...Array(5)].map((_, i) => (
									<div key={i} className="px-5 py-4 animate-pulse flex gap-3">
										<div className="flex-1 space-y-2">
											<div className="w-24 h-4 bg-slate-100 rounded" />
											<div className="w-48 h-3 bg-slate-100 rounded" />
										</div>
										<div className="w-12 h-3 bg-slate-100 rounded mt-1" />
									</div>
								))}
							</div>
						) : translations.length === 0 ? (
							<div className="flex flex-col items-center justify-center py-16 text-slate-300">
								<svg
									className="w-12 h-12 mb-3"
									fill="none"
									stroke="currentColor"
									viewBox="0 0 24 24"
								>
									<path
										strokeLinecap="round"
										strokeLinejoin="round"
										strokeWidth="1.5"
										d="M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129"
									/>
								</svg>
								<p className="text-sm font-semibold">
									翻訳・解説履歴はありません
								</p>
								<p className="text-xs mt-1 text-center">
									辞書タブで単語を保存すると履歴が表示されます
								</p>
							</div>
						) : (
							<div className="divide-y divide-slate-100">
								{translations.map((t, i) => (
									<div
										key={`${t.term}-${i}`}
										className="px-5 py-4 hover:bg-slate-50 transition-colors"
									>
										<div className="flex items-start justify-between gap-3">
											<div className="flex-1 min-w-0">
												<p className="font-semibold text-slate-700 text-sm">
													{t.term}
												</p>
												{t.note && (
													<p className="text-xs text-slate-400 mt-0.5 line-clamp-2">
														{t.note}
													</p>
												)}
											</div>
											<div className="text-right shrink-0">
												{t.page_number != null && (
													<span className="text-xs text-slate-300">
														P.{t.page_number}
													</span>
												)}
												<p className="text-[10px] text-slate-300 mt-0.5">
													{new Date(t.created_at).toLocaleDateString("ja-JP", {
														month: "short",
														day: "numeric",
													})}
												</p>
											</div>
										</div>
									</div>
								))}
							</div>
						)}

						{/* Pagination */}
						{totalPages > 1 && (
							<div className="border-t border-slate-200 px-5 py-3 flex items-center justify-between">
								<button
									type="button"
									onClick={() => setPage((p) => Math.max(1, p - 1))}
									disabled={page <= 1}
									className="text-xs font-semibold text-orange-600 disabled:text-slate-300 hover:underline disabled:no-underline"
								>
									← 前へ
								</button>
								<span className="text-xs text-slate-400">
									{page} / {totalPages}
								</span>
								<button
									type="button"
									onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
									disabled={page >= totalPages}
									className="text-xs font-semibold text-orange-600 disabled:text-slate-300 hover:underline disabled:no-underline"
								>
									次へ →
								</button>
							</div>
						)}
					</div>
				</section>
			</main>
		</div>
	);
}

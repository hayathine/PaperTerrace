import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { useDashboardData } from "@/hooks/useDashboardData";
import type { PaperEntry } from "@/lib/dashboard";
import { createLogger } from "@/lib/logger";

const log = createLogger("Dashboard");

// ─── Shared UI primitives ────────────────────────────────────────────────────

function SectionHeading({ title, count }: { title: string; count?: number }) {
	return (
		<div className="flex items-center justify-between mb-3">
			<h2 className="text-xs font-bold uppercase tracking-wider text-slate-400">
				{title}
			</h2>
			{count != null && (
				<span className="text-xs text-slate-400">{count} 件</span>
			)}
		</div>
	);
}

function EmptyState({
	icon,
	title,
	description,
	py = "py-16",
}: {
	icon: React.ReactNode;
	title: string;
	description?: React.ReactNode;
	py?: string;
}) {
	return (
		<div
			className={`flex flex-col items-center justify-center ${py} text-slate-300`}
		>
			{icon}
			<p className="text-sm font-semibold mt-3">{title}</p>
			{description && <p className="text-xs mt-1 text-center">{description}</p>}
		</div>
	);
}

type TagColor = "orange" | "purple";
const TAG_COLORS: Record<TagColor, string> = {
	orange: "bg-orange-50 text-orange-600 border-orange-100",
	purple: "bg-purple-50 text-purple-600 border-purple-100",
};

function TagChip({
	label,
	color = "orange",
}: {
	label: string;
	color?: TagColor;
}) {
	return (
		<span
			className={`text-xs px-2 py-0.5 rounded-full border ${TAG_COLORS[color]}`}
		>
			{label}
		</span>
	);
}

type PersonaColor = "blue" | "orange" | "green" | "purple";
const PERSONA_COLORS: Record<PersonaColor, { bg: string; icon: string }> = {
	blue: { bg: "bg-blue-50", icon: "text-blue-500" },
	orange: { bg: "bg-orange-50", icon: "text-orange-500" },
	green: { bg: "bg-green-50", icon: "text-green-500" },
	purple: { bg: "bg-purple-50", icon: "text-purple-500" },
};

function PersonaRow({
	color,
	label,
	icon,
	children,
}: {
	color: PersonaColor;
	label: string;
	icon: React.ReactNode;
	children: React.ReactNode;
}) {
	const { bg, icon: iconColor } = PERSONA_COLORS[color];
	return (
		<div className="flex items-start gap-3">
			<div
				className={`w-8 h-8 rounded-xl ${bg} flex items-center justify-center ${iconColor} shrink-0 mt-0.5`}
			>
				{icon}
			</div>
			<div>
				<p className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-0.5">
					{label}
				</p>
				{children}
			</div>
		</div>
	);
}

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

// ─── Skeleton helpers ─────────────────────────────────────────────────────────

function StatSkeleton() {
	return (
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
	);
}

function ListSkeleton({ rows = 4 }: { rows?: number }) {
	return (
		<div className="divide-y divide-slate-100">
			{[...Array(rows)].map((_, i) => (
				<div key={i} className="px-5 py-4 animate-pulse flex gap-3">
					<div className="w-8 h-8 rounded-lg bg-slate-100 shrink-0" />
					<div className="flex-1 space-y-2 py-1">
						<div className="w-3/4 h-3.5 bg-slate-100 rounded" />
						<div className="w-1/3 h-2.5 bg-slate-100 rounded" />
					</div>
				</div>
			))}
		</div>
	);
}

// ─── Icons (shared paths) ─────────────────────────────────────────────────────

const ICON_PAPER_PATH =
	"M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z";
const ICON_TRASH_PATH =
	"M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16";

function IconPaper({ className = "w-5 h-5" }: { className?: string }) {
	return (
		<svg
			className={className}
			fill="none"
			stroke="currentColor"
			viewBox="0 0 24 24"
		>
			<path
				strokeLinecap="round"
				strokeLinejoin="round"
				strokeWidth="2"
				d={ICON_PAPER_PATH}
			/>
		</svg>
	);
}

function IconTrash({ className = "w-3.5 h-3.5" }: { className?: string }) {
	return (
		<svg
			className={className}
			fill="none"
			stroke="currentColor"
			viewBox="0 0 24 24"
		>
			<path
				strokeLinecap="round"
				strokeLinejoin="round"
				strokeWidth="2"
				d={ICON_TRASH_PATH}
			/>
		</svg>
	);
}

// ─── Dashboard ────────────────────────────────────────────────────────────────

export default function Dashboard() {
	const { user, token } = useAuth();
	const navigate = useNavigate();

	const {
		stats,
		statsLoading,
		papers,
		papersLoading,
		removePaper,
		persona,
		bookmarks,
		removeBookmark,
		translations,
		totalTranslations,
		translationsLoading,
		translationPage,
		setTranslationPage,
		totalPages,
	} = useDashboardData(token, user?.id);

	// UI-only state for paper delete confirmation
	const [paperSearch, setPaperSearch] = useState("");
	const [deletingPaperId, setDeletingPaperId] = useState<string | null>(null);
	const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

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

	const handleDeletePaper = async (paperId: string) => {
		setDeletingPaperId(paperId);
		setConfirmDeleteId(null);
		try {
			await removePaper(paperId);
		} catch (e) {
			log.error("delete_paper", "Failed to delete paper", { e });
		} finally {
			setDeletingPaperId(null);
		}
	};

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
						<IconPaper className="w-4 h-4 text-white" />
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

				{/* User Persona */}
				<section>
					<SectionHeading title="あなたのペルソナ" />
					<div className="bg-white rounded-2xl p-5 shadow-sm border border-slate-200">
						{persona ? (
							<div className="space-y-4">
								{persona.knowledge_level && (
									<PersonaRow
										color="blue"
										label="専門レベル"
										icon={
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
													d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
												/>
											</svg>
										}
									>
										<p className="text-sm text-slate-700">
											{persona.knowledge_level}
										</p>
									</PersonaRow>
								)}
								{Array.isArray(persona.interests) &&
									persona.interests.length > 0 && (
										<PersonaRow
											color="orange"
											label="興味分野"
											icon={
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
														d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"
													/>
												</svg>
											}
										>
											<div className="flex flex-wrap gap-1.5 mt-1">
												{(persona.interests as string[]).map((interest) => (
													<TagChip key={interest} label={interest} />
												))}
											</div>
										</PersonaRow>
									)}
								{persona.preferred_direction && (
									<PersonaRow
										color="green"
										label="好みの説明スタイル"
										icon={
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
													d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
												/>
											</svg>
										}
									>
										<p className="text-sm text-slate-700">
											{persona.preferred_direction}
										</p>
									</PersonaRow>
								)}
								{Array.isArray(persona.unknown_concepts) &&
									persona.unknown_concepts.length > 0 && (
										<PersonaRow
											color="purple"
											label="学習中の概念"
											icon={
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
														d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
													/>
												</svg>
											}
										>
											<div className="flex flex-wrap gap-1.5 mt-1">
												{(persona.unknown_concepts as string[])
													.slice(0, 8)
													.map((concept) => (
														<TagChip
															key={concept}
															label={concept}
															color="purple"
														/>
													))}
											</div>
										</PersonaRow>
									)}
								{persona.updated_at && (
									<p className="text-[10px] text-slate-300 text-right pt-1">
										{new Date(persona.updated_at).toLocaleDateString("ja-JP", {
											year: "numeric",
											month: "short",
											day: "numeric",
										})}{" "}
										更新
									</p>
								)}
							</div>
						) : (
							<EmptyState
								py="py-8"
								icon={
									<svg
										className="w-10 h-10"
										fill="none"
										stroke="currentColor"
										viewBox="0 0 24 24"
									>
										<path
											strokeLinecap="round"
											strokeLinejoin="round"
											strokeWidth="1.5"
											d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
										/>
									</svg>
								}
								title="ペルソナ未生成"
								description={
									<>
										論文を読んで推薦を受けると
										<br />
										あなたのペルソナが作成されます
									</>
								}
							/>
						)}
					</div>
				</section>

				{/* Stats */}
				<section>
					<SectionHeading title="学習サマリー" />
					{statsLoading ? (
						<StatSkeleton />
					) : (
						<div className="flex gap-3 overflow-x-auto pb-1">
							<StatCard
								label="読んだ論文"
								value={stats?.paper_count ?? 0}
								icon={<IconPaper />}
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
					<SectionHeading
						title="読んだ論文"
						count={papers.length > 0 ? papers.length : undefined}
					/>
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
							<ListSkeleton rows={4} />
						) : filteredPapers.length === 0 ? (
							<EmptyState
								icon={<IconPaper className="w-12 h-12" />}
								title={
									paperSearch
										? "一致する論文がありません"
										: "論文はまだありません"
								}
								description={
									!paperSearch
										? "PDFをアップロードして読み始めましょう"
										: undefined
								}
							/>
						) : (
							<div className="divide-y divide-slate-100">
								{filteredPapers.map((p) => (
									<PaperRow
										key={p.paper_id}
										paper={p}
										isDeleting={deletingPaperId === p.paper_id}
										isConfirming={confirmDeleteId === p.paper_id}
										onNavigate={() => navigate(`/paper/${p.paper_id}`)}
										onRequestDelete={() => setConfirmDeleteId(p.paper_id)}
										onConfirmDelete={() => handleDeletePaper(p.paper_id)}
										onCancelDelete={() => setConfirmDeleteId(null)}
									/>
								))}
							</div>
						)}
					</div>
				</section>

				{/* Bookmarks */}
				{bookmarks.length > 0 && (
					<section>
						<SectionHeading title="しおり" count={bookmarks.length} />
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
											onClick={() => bm.id != null && removeBookmark(bm.id)}
											className="p-1.5 rounded-lg text-slate-300 hover:text-red-400 hover:bg-red-50 transition-colors shrink-0"
											title="しおりを削除"
										>
											<IconTrash />
										</button>
									</div>
								))}
							</div>
						</div>
					</section>
				)}

				{/* Translation History */}
				<section>
					<SectionHeading
						title="翻訳・解説履歴"
						count={totalTranslations > 0 ? totalTranslations : undefined}
					/>
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
							<EmptyState
								icon={
									<svg
										className="w-12 h-12"
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
								}
								title="翻訳・解説履歴はありません"
								description="辞書タブで単語を保存すると履歴が表示されます"
							/>
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
						{totalPages > 1 && (
							<div className="border-t border-slate-200 px-5 py-3 flex items-center justify-between">
								<button
									type="button"
									onClick={() => setTranslationPage((p) => Math.max(1, p - 1))}
									disabled={translationPage <= 1}
									className="text-xs font-semibold text-orange-600 disabled:text-slate-300 hover:underline disabled:no-underline"
								>
									← 前へ
								</button>
								<span className="text-xs text-slate-400">
									{translationPage} / {totalPages}
								</span>
								<button
									type="button"
									onClick={() =>
										setTranslationPage((p) => Math.min(totalPages, p + 1))
									}
									disabled={translationPage >= totalPages}
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

// ─── PaperRow ─────────────────────────────────────────────────────────────────

function PaperRow({
	paper,
	isDeleting,
	isConfirming,
	onNavigate,
	onRequestDelete,
	onConfirmDelete,
	onCancelDelete,
}: {
	paper: PaperEntry;
	isDeleting: boolean;
	isConfirming: boolean;
	onNavigate: () => void;
	onRequestDelete: () => void;
	onConfirmDelete: () => void;
	onCancelDelete: () => void;
}) {
	return (
		<div className="w-full px-5 py-4 hover:bg-orange-50 transition-colors flex items-center gap-3 group">
			<button
				type="button"
				onClick={onNavigate}
				className="flex items-center gap-3 flex-1 min-w-0 text-left"
			>
				<div className="w-8 h-8 rounded-lg bg-orange-50 group-hover:bg-orange-100 flex items-center justify-center text-orange-500 shrink-0 transition-colors">
					<IconPaper className="w-4 h-4" />
				</div>
				<div className="flex-1 min-w-0">
					<p className="text-sm font-semibold text-slate-700 truncate group-hover:text-orange-700 transition-colors">
						{paper.title ?? "タイトル未設定"}
					</p>
					<div className="flex items-center gap-2 mt-0.5">
						<p className="text-xs text-slate-400">
							{new Date(paper.created_at).toLocaleDateString("ja-JP", {
								year: "numeric",
								month: "short",
								day: "numeric",
							})}
						</p>
						{Array.isArray(paper.tags) && paper.tags.length > 0 && (
							<div className="flex gap-1 flex-wrap">
								{(paper.tags as string[]).slice(0, 3).map((tag) => (
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
			{isConfirming ? (
				<div className="flex items-center gap-1 shrink-0">
					<button
						type="button"
						onClick={onConfirmDelete}
						className="text-[10px] font-semibold px-2 py-1 rounded-lg bg-red-100 text-red-600 hover:bg-red-200 transition-colors"
					>
						削除
					</button>
					<button
						type="button"
						onClick={onCancelDelete}
						className="text-[10px] font-semibold px-2 py-1 rounded-lg bg-slate-100 text-slate-500 hover:bg-slate-200 transition-colors"
					>
						戻る
					</button>
				</div>
			) : (
				<button
					type="button"
					onClick={onRequestDelete}
					disabled={isDeleting}
					className="p-1.5 rounded-lg text-slate-300 hover:text-red-400 hover:bg-red-50 transition-colors shrink-0 opacity-0 group-hover:opacity-100"
					title="論文を削除"
				>
					{isDeleting ? (
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
						<IconTrash />
					)}
				</button>
			)}
		</div>
	);
}

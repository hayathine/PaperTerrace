import type React from "react";
import { useCallback, useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";

/**
 * 検索マッチの位置情報
 */
export interface SearchMatch {
	page: number;
	wordIndex: number;
}

interface SearchBarProps {
	// 検索バーの表示状態
	isOpen: boolean;
	onClose: () => void;

	// 検索語
	searchTerm: string;
	onSearchTermChange: (term: string) => void;

	// マッチ結果
	matches: SearchMatch[];
	currentMatchIndex: number;
	onNextMatch: () => void;
	onPrevMatch: () => void;
}

/**
 * カスタム検索バーコンポーネント
 * Ctrl+Fで表示され、PDF内のテキスト検索を行う
 */
const SearchBar: React.FC<SearchBarProps> = ({
	isOpen,
	onClose,
	searchTerm,
	onSearchTermChange,
	matches,
	currentMatchIndex,
	onNextMatch,
	onPrevMatch,
}) => {
	const { t } = useTranslation();
	const inputRef = useRef<HTMLInputElement>(null);

	// 検索バーが開いたらフォーカス
	useEffect(() => {
		if (isOpen && inputRef.current) {
			inputRef.current.focus();
			inputRef.current.select();
		}
	}, [isOpen]);

	// キーボードショートカット
	const handleKeyDown = useCallback(
		(e: React.KeyboardEvent) => {
			if (e.key === "Escape") {
				onClose();
			} else if (e.key === "Enter") {
				if (e.shiftKey) {
					onPrevMatch();
				} else {
					onNextMatch();
				}
			}
		},
		[onClose, onNextMatch, onPrevMatch],
	);

	if (!isOpen) return null;

	return (
		<div className="fixed top-16 right-4 z-[100] animate-in slide-in-from-top-2 duration-200">
			<div className="bg-white rounded-xl shadow-2xl border border-slate-200 overflow-hidden">
				{/* 検索入力エリア */}
				<div className="flex items-center gap-2 p-3 bg-slate-50 border-b border-slate-100">
					{/* 検索アイコン */}
					<svg
						className="w-4 h-4 text-slate-400 shrink-0"
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

					{/* 入力フィールド */}
					<input
						ref={inputRef}
						type="text"
						value={searchTerm}
						onChange={(e) => onSearchTermChange(e.target.value)}
						onKeyDown={handleKeyDown}
						placeholder={t("search.placeholder", "検索...")}
						className="flex-1 min-w-[200px] bg-transparent text-sm text-slate-700 placeholder-slate-400 outline-none"
					/>

					{/* 結果カウント */}
					{searchTerm && (
						<span className="text-xs text-slate-500 tabular-nums shrink-0 px-2 py-0.5 bg-slate-100 rounded-full">
							{matches.length > 0
								? `${currentMatchIndex + 1} / ${matches.length}`
								: t("search.no_results", "0件")}
						</span>
					)}
				</div>

				{/* ナビゲーションボタン */}
				<div className="flex items-center justify-between p-2 bg-white">
					<div className="flex items-center gap-1">
						{/* 前へ */}
						<button
							onClick={onPrevMatch}
							disabled={matches.length === 0}
							className="p-1.5 rounded-lg hover:bg-slate-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
							title={t("search.prev", "前へ (Shift+Enter)")}
						>
							<svg
								className="w-4 h-4 text-slate-600"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
							>
								<path
									strokeLinecap="round"
									strokeLinejoin="round"
									strokeWidth="2"
									d="M5 15l7-7 7 7"
								/>
							</svg>
						</button>

						{/* 次へ */}
						<button
							onClick={onNextMatch}
							disabled={matches.length === 0}
							className="p-1.5 rounded-lg hover:bg-slate-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
							title={t("search.next", "次へ (Enter)")}
						>
							<svg
								className="w-4 h-4 text-slate-600"
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
						</button>
					</div>

					{/* 閉じるボタン */}
					<button
						onClick={onClose}
						className="p-1.5 rounded-lg hover:bg-red-50 text-slate-400 hover:text-red-500 transition-colors"
						title={t("search.close", "閉じる (Esc)")}
					>
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
								d="M6 18L18 6M6 6l12 12"
							/>
						</svg>
					</button>
				</div>

				{/* ヒント */}
				{searchTerm && matches.length > 0 && (
					<div className="px-3 py-1.5 bg-indigo-50 border-t border-indigo-100">
						<p className="text-[10px] text-indigo-600 font-medium">
							💡 Enter: {t("search.hint_next", "次へ")} / Shift+Enter:{" "}
							{t("search.hint_prev", "前へ")}
						</p>
					</div>
				)}
			</div>
		</div>
	);
};

export default SearchBar;

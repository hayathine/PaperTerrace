import { useCallback, useEffect, useState } from "react";

/**
 * PDF 内テキスト検索に関連する状態と操作をまとめたカスタムフック。
 */
export function useSearchState(hasDocument: boolean, onClose?: () => void) {
	const [isSearchOpen, setIsSearchOpen] = useState(false);
	const [searchTerm, setSearchTerm] = useState("");
	const [searchMatches, setSearchMatches] = useState<
		Array<{ page: number; wordIndex: number }>
	>([]);
	const [currentMatchIndex, setCurrentMatchIndex] = useState(0);

	const currentSearchMatch =
		searchMatches.length > 0 && currentMatchIndex < searchMatches.length
			? searchMatches[currentMatchIndex]
			: null;

	const handleNextMatch = useCallback(() => {
		if (searchMatches.length === 0) return;
		setCurrentMatchIndex((prev) => (prev + 1) % searchMatches.length);
	}, [searchMatches.length]);

	const handlePrevMatch = useCallback(() => {
		if (searchMatches.length === 0) return;
		setCurrentMatchIndex(
			(prev) => (prev - 1 + searchMatches.length) % searchMatches.length,
		);
	}, [searchMatches.length]);

	const handleCloseSearch = useCallback(() => {
		setIsSearchOpen(false);
		setSearchTerm("");
		setSearchMatches([]);
		setCurrentMatchIndex(0);
		onClose?.();
	}, [onClose]);

	const handleSearchMatchesUpdate = useCallback(
		(matches: Array<{ page: number; wordIndex: number }>) => {
			setSearchMatches(matches);
			setCurrentMatchIndex(0);
		},
		[],
	);

	// Ctrl+F / Cmd+F のインターセプト
	useEffect(() => {
		const handleKeyDown = (e: KeyboardEvent) => {
			if ((e.ctrlKey || e.metaKey) && e.key === "f") {
				if (hasDocument) {
					e.preventDefault();
					setIsSearchOpen(true);
				}
			}
			if (e.key === "Escape" && isSearchOpen) {
				handleCloseSearch();
			}
		};

		window.addEventListener("keydown", handleKeyDown);
		return () => window.removeEventListener("keydown", handleKeyDown);
	}, [hasDocument, isSearchOpen, handleCloseSearch]);

	return {
		isSearchOpen,
		setIsSearchOpen,
		searchTerm,
		setSearchTerm,
		searchMatches,
		currentMatchIndex,
		currentSearchMatch,
		handleNextMatch,
		handlePrevMatch,
		handleCloseSearch,
		handleSearchMatchesUpdate,
	};
}

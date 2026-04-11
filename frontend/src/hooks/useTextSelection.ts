import { useEffect, useRef, useState } from "react";

export interface SelectionMenuState {
	x: number;
	y: number;
	text: string;
	context: string;
	coords: { page: number; x: number; y: number };
}

/**
 * テキスト選択メニューの表示・非表示を管理するカスタムフック。
 * mouseup/touchend でテキスト選択を検出し、selection-menu 外クリックで閉じる。
 *
 * @param pageNum - 現在のページ番号（コンテナ ID `text-page-{pageNum}` の特定に使用）
 */
export function useTextSelection(pageNum: number) {
	const [selectionMenu, setSelectionMenu] = useState<SelectionMenuState | null>(
		null,
	);
	const selectionTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

	// --- テキスト選択メニュー ---
	useEffect(() => {
		const handleSelectionEnd = () => {
			// 前のタイマーをキャンセルして競合状態を防ぐ
			if (selectionTimerRef.current !== null) {
				clearTimeout(selectionTimerRef.current);
			}
			selectionTimerRef.current = setTimeout(() => {
				selectionTimerRef.current = null;
				const selection = window.getSelection();
				const selectionText = selection?.toString().trim();
				const container = document.getElementById(`text-page-${pageNum}`);

				if (
					selection &&
					selection.rangeCount > 0 &&
					selectionText &&
					selectionText.length > 0 &&
					container
				) {
					const range = selection.getRangeAt(0);

					if (
						!container.contains(range.startContainer) &&
						range.startContainer !== container
					) {
						return;
					}

					const rect = container.getBoundingClientRect();
					const rangeRect = range.getBoundingClientRect();

					if (rangeRect.width === 0) return;

					const pageWidth = rect.width || 1;
					const pageHeight = rect.height || 1;

					// Clamp menu X to avoid overflow near screen edges (10%–90% of page width)
					const rawMenuX =
						(((rangeRect.left + rangeRect.right) / 2 - rect.left) / pageWidth) *
						100;
					const menuX = Math.max(10, Math.min(90, rawMenuX));
					const menuY = ((rangeRect.bottom - rect.top) / pageHeight) * 100;

					const centerX =
						((rangeRect.left + rangeRect.right) / 2 - rect.left) / pageWidth;
					const centerY =
						((rangeRect.top + rangeRect.bottom) / 2 - rect.top) / pageHeight;

					// Extract context text (parent paragraph or surrounding text)
					let contextText = selectionText;
					let currentEl = range.startContainer.parentElement;
					while (currentEl && currentEl !== container) {
						if (
							["P", "LI", "H1", "H2", "H3", "H4", "H5", "H6"].includes(
								currentEl.tagName,
							)
						) {
							contextText = currentEl.textContent || selectionText;
							break;
						}
						currentEl = currentEl.parentElement;
					}

					setSelectionMenu({
						x: menuX,
						y: menuY,
						text: selectionText,
						context: contextText,
						coords: { page: pageNum, x: centerX, y: centerY },
					});
				} else {
					setSelectionMenu(null);
				}
			}, 10);
		};

		// Support both mouse and touch text selection
		document.addEventListener("mouseup", handleSelectionEnd);
		document.addEventListener("touchend", handleSelectionEnd);
		return () => {
			document.removeEventListener("mouseup", handleSelectionEnd);
			document.removeEventListener("touchend", handleSelectionEnd);
			// アンマウント時に残存タイマーをキャンセル
			if (selectionTimerRef.current !== null) {
				clearTimeout(selectionTimerRef.current);
			}
		};
	}, [pageNum]);

	useEffect(() => {
		const handleClickOutside = (e: MouseEvent) => {
			if ((e.target as HTMLElement).closest(".selection-menu")) return;
			setSelectionMenu(null);
		};
		if (selectionMenu)
			document.addEventListener("mousedown", handleClickOutside);
		return () => document.removeEventListener("mousedown", handleClickOutside);
	}, [selectionMenu]);

	return {
		selectionMenu,
		clearSelectionMenu: () => setSelectionMenu(null),
	};
}

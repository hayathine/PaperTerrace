import { useEffect, useState } from "react";

const DEFAULT_SIDEBAR_WIDTH = 384;
const MIN_SIDEBAR_WIDTH = 150;
/** PDF ビューアーに確保する最小幅 (px) */
const MIN_PDF_WIDTH = 250;
const LEFT_SIDEBAR_WIDTH = 256;
const RESIZER_WIDTH = 6;

/** 右サイドバーの幅を viewport に収まる範囲にクランプする */
function clampWidth(
	width: number,
	viewportWidth: number,
	leftOpen: boolean,
): number {
	const leftWidth = leftOpen ? LEFT_SIDEBAR_WIDTH : 0;
	const maxAllowed = viewportWidth - leftWidth - MIN_PDF_WIDTH - RESIZER_WIDTH;
	return Math.max(MIN_SIDEBAR_WIDTH, Math.min(width, maxAllowed));
}

/**
 * サイドバーレイアウトに関連する状態とリサイズロジックを管理するカスタムフック。
 */
export function useLayoutState() {
	const [sidebarWidth, setSidebarWidth] = useState(() =>
		clampWidth(
			DEFAULT_SIDEBAR_WIDTH,
			window.innerWidth,
			window.innerWidth >= 768,
		),
	);
	const [isResizing, setIsResizing] = useState(false);
	const [isLeftSidebarOpen, setIsLeftSidebarOpen] = useState(
		() => window.innerWidth >= 768,
	);
	const [isRightSidebarOpen, setIsRightSidebarOpen] = useState(false);
	const [isMobile, setIsMobile] = useState(() => window.innerWidth < 768);

	// ブレークポイント監視
	useEffect(() => {
		const checkMobile = () => {
			const mobile = window.innerWidth < 768;
			setIsMobile(mobile);
			if (mobile) {
				setIsRightSidebarOpen(false);
				setIsLeftSidebarOpen(false);
			}
		};
		window.addEventListener("resize", checkMobile);
		return () => window.removeEventListener("resize", checkMobile);
	}, []);

	// ウィンドウリサイズ時に右サイドバー幅を自動調整（ブラウザ独自サイドバー等で viewport が狭まった場合に対応）
	useEffect(() => {
		const adjustWidth = () => {
			if (window.innerWidth < 768) return;
			setSidebarWidth((prev) =>
				clampWidth(prev, window.innerWidth, isLeftSidebarOpen),
			);
		};
		window.addEventListener("resize", adjustWidth);
		return () => window.removeEventListener("resize", adjustWidth);
	}, [isLeftSidebarOpen]);

	// サイドバーリサイズ
	useEffect(() => {
		const handleMouseMove = (e: MouseEvent) => {
			if (!isResizing) return;
			const newWidth = window.innerWidth - e.clientX;
			const leftWidth = isLeftSidebarOpen ? LEFT_SIDEBAR_WIDTH : 0;
			const maxAllowed = Math.min(
				window.innerWidth * 0.7,
				window.innerWidth - leftWidth - MIN_PDF_WIDTH - RESIZER_WIDTH,
			);
			if (newWidth > MIN_SIDEBAR_WIDTH && newWidth < maxAllowed) {
				setSidebarWidth(newWidth);
			}
		};
		const handleMouseUp = () => {
			setIsResizing(false);
			document.body.style.cursor = "default";
			document.body.style.userSelect = "auto";
		};

		if (isResizing) {
			window.addEventListener("mousemove", handleMouseMove);
			window.addEventListener("mouseup", handleMouseUp);
			document.body.style.cursor = "col-resize";
			document.body.style.userSelect = "none";
		}

		return () => {
			window.removeEventListener("mousemove", handleMouseMove);
			window.removeEventListener("mouseup", handleMouseUp);
		};
	}, [isResizing, isLeftSidebarOpen]);

	return {
		sidebarWidth,
		setSidebarWidth,
		isResizing,
		setIsResizing,
		isLeftSidebarOpen,
		setIsLeftSidebarOpen,
		isRightSidebarOpen,
		setIsRightSidebarOpen,
		isMobile,
	};
}

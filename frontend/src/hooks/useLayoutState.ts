import { useEffect, useState } from "react";

/**
 * サイドバーレイアウトに関連する状態とリサイズロジックを管理するカスタムフック。
 */
export function useLayoutState() {
	const [sidebarWidth, setSidebarWidth] = useState(384);
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

	// サイドバーリサイズ
	useEffect(() => {
		const handleMouseMove = (e: MouseEvent) => {
			if (!isResizing) return;
			const newWidth = window.innerWidth - e.clientX;
			if (newWidth > 200 && newWidth < window.innerWidth * 0.7) {
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
	}, [isResizing]);

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

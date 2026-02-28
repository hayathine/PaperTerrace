import React from "react";
import TextModePage from "./TextModePage";
import type { PageWithLines } from "./types";

interface TextModeViewerProps {
	pages: PageWithLines[];
	onWordClick?: (
		word: string,
		context?: string,
		coords?: { page: number; x: number; y: number },
	) => void;
	onTextSelect?: (
		text: string,
		coords: { page: number; x: number; y: number },
	) => void;
	onAskAI?: (prompt: string, imageUrl?: string, coords?: any) => void;
	searchTerm?: string;
}

const TextModeViewer: React.FC<TextModeViewerProps> = ({
	pages,
	onWordClick,
	onTextSelect,
	onAskAI,
	searchTerm,
}) => {
	if (!pages || pages.length === 0) {
		return (
			<div className="flex flex-col items-center justify-center p-12 text-slate-400">
				<div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500 mb-4"></div>
				<p>読み込み中...</p>
			</div>
		);
	}

	return (
		<div className="w-full max-w-5xl mx-auto p-4 space-y-12 pb-32">
			{pages.map((page) => (
				<TextModePage
					key={page.page_num}
					page={page}
					onWordClick={onWordClick}
					onTextSelect={onTextSelect}
					onAskAI={onAskAI}
					searchTerm={searchTerm}
				/>
			))}
		</div>
	);
};

export default React.memo(TextModeViewer);

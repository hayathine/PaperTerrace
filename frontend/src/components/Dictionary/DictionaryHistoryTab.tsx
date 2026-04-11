import type React from "react";
import { useTranslation } from "react-i18next";
import type { SavedNote } from "../../hooks/useDictionaryHistory";

interface DictionaryHistoryTabProps {
	savedNotes: SavedNote[];
	onSelectNote: () => void;
}

const DictionaryHistoryTab: React.FC<DictionaryHistoryTabProps> = ({
	savedNotes,
	onSelectNote,
}) => {
	const { t } = useTranslation();

	if (savedNotes.length === 0) {
		return (
			<div className="flex flex-col items-center justify-center h-full p-8 text-slate-300">
				<div className="bg-slate-50 p-4 rounded-xl mb-4">
					<svg
						className="w-8 h-8 opacity-50"
						fill="none"
						viewBox="0 0 24 24"
						stroke="currentColor"
					>
						<path
							strokeLinecap="round"
							strokeLinejoin="round"
							strokeWidth={2}
							d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
						/>
					</svg>
				</div>
				<p className="text-xs font-bold uppercase tracking-wider">
					{t("viewer.dictionary.history_empty")}
				</p>
				<p className="text-[10px] mt-2 text-center">
					{t("viewer.dictionary.history_hint")}
				</p>
			</div>
		);
	}

	return (
		<div className="space-y-2">
			{savedNotes.map((note) => (
				<button
					key={note.note_id}
					type="button"
					onClick={onSelectNote}
					className="w-full text-left bg-white border border-slate-100 rounded-xl p-3 hover:shadow-md hover:border-orange-200 transition-all group"
				>
					<div className="flex items-start justify-between gap-2">
						<span className="text-sm font-bold text-slate-800 group-hover:text-orange-600 transition-colors truncate">
							{note.term}
						</span>
						{note.page_number != null && (
							<span className="text-[9px] bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded-full shrink-0">
								p.{note.page_number}
							</span>
						)}
					</div>
					<p className="text-[11px] text-slate-500 mt-1 line-clamp-2 leading-relaxed">
						{note.note}
					</p>
				</button>
			))}
		</div>
	);
};

export default DictionaryHistoryTab;

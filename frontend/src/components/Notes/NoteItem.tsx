import type React from "react";
import { useTranslation } from "react-i18next";
import type { Note } from "./types";

interface NoteItemProps {
	note: Note;
	onDelete: (id: string) => void;
	onJump?: (page: number, x: number, y: number, term?: string) => void;
}

const NoteItem: React.FC<NoteItemProps> = ({ note, onDelete, onJump }) => {
	const { t } = useTranslation();
	return (
		<div className="bg-white p-3 rounded-xl border border-slate-100 shadow-sm overflow-hidden group mb-3 hover:shadow-md transition-all">
			<div className="flex justify-between items-start">
				<span className="font-bold text-xs text-indigo-600 break-words">
					{note.term}
				</span>
				<button
					type="button"
					onClick={() => onDelete(note.note_id)}
					className="text-slate-300 hover:text-red-500 text-xs px-1 opacity-0 group-hover:opacity-100 transition-opacity"
					title="Delete Note"
				>
					×
				</button>
			</div>

			{note.image_url && (
				<div className="mt-2 rounded-lg overflow-hidden border border-slate-50">
					<img
						src={note.image_url}
						alt="Note Attachment"
						className="w-full h-auto object-cover max-h-40"
						loading="lazy"
					/>
				</div>
			)}

			<p className="text-[10px] text-slate-500 mt-1 whitespace-pre-wrap leading-relaxed">
				{note.note}
			</p>

			{note.page_number !== undefined && note.page_number !== null && (
				<div className="mt-2 flex justify-start">
					<button
						type="button"
						onClick={() =>
							onJump &&
							note.page_number !== undefined &&
							onJump(note.page_number, note.x || 0.5, note.y || 0.5, note.term)
						}
						className="flex items-center gap-1.5 text-[10px] py-1 px-2 bg-indigo-50 text-indigo-600 rounded-md hover:bg-indigo-100 transition-colors"
					>
						<svg
							xmlns="http://www.w3.org/2000/svg"
							className="h-3 w-3"
							fill="none"
							viewBox="0 0 24 24"
							stroke="currentColor"
						>
							<path
								strokeLinecap="round"
								strokeLinejoin="round"
								strokeWidth={2}
								d="M13 5l7 7-7 7M5 5l7 7-7 7"
							/>
						</svg>
						{t("notes.jump_to_page", { page: note.page_number })}
					</button>
				</div>
			)}

			{note.created_at && (
				<div className="text-[9px] text-slate-300 mt-2 text-right">
					{new Date(note.created_at).toLocaleString()}
				</div>
			)}
		</div>
	);
};

export default NoteItem;

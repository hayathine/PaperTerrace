import React, { useState } from "react";
import { useTranslation } from "react-i18next";

interface AddNoteFormProps {
	onAdd: (
		term: string,
		note: string,
		coords?: { page: number; x: number; y: number },
		imageUrl?: string,
	) => Promise<void>;
	onUpdate?: (
		id: string,
		term: string,
		note: string,
		coords?: { page: number; x: number; y: number },
		imageUrl?: string,
	) => Promise<void>;
	onCancelEdit?: () => void;
	coordinates?: { page: number; x: number; y: number };
	initialContent?: string;
	initialTerm?: string;
	initialImage?: string;
	editingNote?: {
		id: string;
		term: string;
		note: string;
		page_number?: number;
		x?: number;
		y?: number;
		image_url?: string;
	} | null;
}

const AddNoteForm: React.FC<AddNoteFormProps> = ({
	onAdd,
	onUpdate,
	onCancelEdit,
	coordinates,
	initialContent = "",
	initialTerm = "",
	initialImage = "",
	editingNote = null,
}) => {
	const { t } = useTranslation();
	const [term, setTerm] = useState(initialTerm);

	const [note, setNote] = useState(initialContent);
	const [imageUrl, setImageUrl] = useState<string | undefined>(initialImage);
	const [isSubmitting, setIsSubmitting] = useState(false);

	// Effect for handling selection text/image injection
	React.useEffect(() => {
		if (!editingNote) {
			if (initialContent) setNote(initialContent);
			if (initialTerm) setTerm(initialTerm);
			if (initialImage) setImageUrl(initialImage);
		}
	}, [initialContent, initialTerm, initialImage, editingNote]);

	// Effect for handling edit mode
	React.useEffect(() => {
		if (editingNote) {
			setTerm(editingNote.term);
			setNote(editingNote.note);
			setImageUrl(editingNote.image_url);
		} else if (!initialContent && !initialTerm && !initialImage) {
			setTerm("");
			setNote("");
			setImageUrl(undefined);
		}
	}, [editingNote]);

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		if (!term.trim() || (!note.trim() && !imageUrl)) return;

		setIsSubmitting(true);
		try {
			if (editingNote && onUpdate) {
				await onUpdate(editingNote.id, term, note, coordinates, imageUrl);
			} else {
				await onAdd(term, note, coordinates, imageUrl);
			}

			if (!editingNote) {
				setTerm("");
				setNote("");
				setImageUrl(undefined);
			}
		} finally {
			setIsSubmitting(false);
		}
	};

	return (
		<form
			onSubmit={handleSubmit}
			className="mb-6 bg-slate-50 p-3 rounded-xl border border-slate-100"
		>
			{imageUrl && (
				<div className="relative mb-3 group">
					<img
						src={imageUrl}
						alt="Attached snippet"
						className="w-full h-auto rounded-lg border border-slate-200 shadow-sm"
					/>
					<button
						type="button"
						onClick={() => setImageUrl(undefined)}
						className="absolute top-1 right-1 bg-black/50 hover:bg-black/70 text-white rounded-full p-1 opacity-0 group-hover:opacity-100 transition-opacity"
					>
						<svg
							className="w-3 h-3"
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
			)}

			<div className="relative">
				<input
					type="text"
					placeholder={t("notes.placeholder_term")}
					className="w-full text-xs font-bold text-slate-700 bg-white border border-slate-200 rounded-lg px-2 py-1.5 mb-2 focus:ring-2 focus:ring-indigo-100 focus:border-indigo-300 outline-none pr-8"
					value={term}
					onChange={(e) => setTerm(e.target.value)}
					disabled={isSubmitting}
				/>
				{coordinates && (
					<div
						className="absolute right-2 top-2 text-indigo-500"
						title="Link to current location"
					>
						<svg
							xmlns="http://www.w3.org/2000/svg"
							className="h-4 w-4"
							fill="none"
							viewBox="0 0 24 24"
							stroke="currentColor"
						>
							<path
								strokeLinecap="round"
								strokeLinejoin="round"
								strokeWidth={2}
								d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 00.5656 0l-4 4a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-4 4"
							/>
							<path
								strokeLinecap="round"
								strokeLinejoin="round"
								strokeWidth={2}
								d="M10.172 13.828a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-4 4a4 4 0 005.656 5.656"
							/>
						</svg>
					</div>
				)}
			</div>
			<textarea
				placeholder={t("notes.placeholder_content")}
				className="w-full text-[10px] text-slate-600 bg-white border border-slate-200 rounded-lg px-2 py-2 mb-2 h-16 resize-none focus:ring-2 focus:ring-indigo-100 focus:border-indigo-300 outline-none"
				value={note}
				onChange={(e) => setNote(e.target.value)}
				disabled={isSubmitting}
			/>
			<div className="flex gap-2">
				{editingNote && onCancelEdit && (
					<button
						type="button"
						onClick={onCancelEdit}
						disabled={isSubmitting}
						className="flex-1 py-1.5 bg-slate-200 hover:bg-slate-300 text-slate-600 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-colors"
					>
						{t("common.cancel")}
					</button>
				)}
				<button
					type="submit"
					disabled={isSubmitting || !term || (!note && !imageUrl)}
					className="flex-1 py-1.5 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-300 text-white rounded-lg text-[10px] font-bold uppercase tracking-wider transition-colors shadow-sm"
				>
					{isSubmitting
						? editingNote
							? t("notes.updating")
							: t("notes.adding")
						: editingNote
							? t("notes.update")
							: t("notes.add")}
				</button>
			</div>
		</form>
	);
};

export default AddNoteForm;

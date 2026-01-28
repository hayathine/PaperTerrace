import React from 'react';
import { Note } from './types';

interface NoteItemProps {
    note: Note;
    onDelete: (id: string) => void;
}

const NoteItem: React.FC<NoteItemProps> = ({ note, onDelete }) => {
    return (
        <div className="bg-white p-3 rounded-xl border border-slate-100 shadow-sm overflow-hidden group mb-3 hover:shadow-md transition-all">
            <div className="flex justify-between items-start">
                <span className="font-bold text-xs text-indigo-600 break-words">{note.term}</span>
                <button
                    onClick={() => onDelete(note.note_id)}
                    className="text-slate-300 hover:text-red-500 text-xs px-1 opacity-0 group-hover:opacity-100 transition-opacity"
                    title="Delete Note"
                >
                    ×
                </button>
            </div>

            {note.image_url && (
                <div className="mt-2 rounded-lg overflow-hidden border border-slate-50">
                    <img src={note.image_url} alt="Note Attachment" className="w-full h-auto object-cover max-h-40" loading="lazy" />
                </div>
            )}

            <p className="text-[10px] text-slate-500 mt-1 whitespace-pre-wrap leading-relaxed">{note.note}</p>
            {note.created_at && (
                <div className="text-[9px] text-slate-300 mt-2 text-right">
                    {new Date(note.created_at).toLocaleString()}
                </div>
            )}
        </div>
    );
};

export default NoteItem;

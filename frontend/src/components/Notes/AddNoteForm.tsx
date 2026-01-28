import React, { useState } from 'react';

interface AddNoteFormProps {
    onAdd: (term: string, note: string) => Promise<void>;
}

const AddNoteForm: React.FC<AddNoteFormProps> = ({ onAdd }) => {
    const [term, setTerm] = useState('');
    const [note, setNote] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!term.trim() || !note.trim()) return;

        setIsSubmitting(true);
        try {
            await onAdd(term, note);
            setTerm('');
            setNote('');
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <form onSubmit={handleSubmit} className="mb-6 bg-slate-50 p-3 rounded-xl border border-slate-100">
            <input
                type="text"
                placeholder="Term / Keyword"
                className="w-full text-xs font-bold text-slate-700 bg-white border border-slate-200 rounded-lg px-2 py-1.5 mb-2 focus:ring-2 focus:ring-indigo-100 focus:border-indigo-300 outline-none"
                value={term}
                onChange={(e) => setTerm(e.target.value)}
                disabled={isSubmitting}
            />
            <textarea
                placeholder="Write your note here..."
                className="w-full text-[10px] text-slate-600 bg-white border border-slate-200 rounded-lg px-2 py-2 mb-2 h-16 resize-none focus:ring-2 focus:ring-indigo-100 focus:border-indigo-300 outline-none"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                disabled={isSubmitting}
            />
            <button
                type="submit"
                disabled={isSubmitting || !term || !note}
                className="w-full py-1.5 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-300 text-white rounded-lg text-[10px] font-bold uppercase tracking-wider transition-colors shadow-sm"
            >
                {isSubmitting ? 'Adding...' : 'Add Note'}
            </button>
        </form>
    );
};

export default AddNoteForm;

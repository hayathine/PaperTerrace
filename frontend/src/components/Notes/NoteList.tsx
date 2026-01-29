import React, { useEffect, useState, useCallback } from 'react';
import { Note } from './types';
import NoteItem from './NoteItem';
import AddNoteForm from './AddNoteForm';
import { useAuth } from '../../contexts/AuthContext';

interface NoteListProps {
    sessionId: string;
    coordinates?: { page: number, x: number, y: number };
    onJump?: (page: number, x: number, y: number) => void;
    selectedContext?: string;
    selectedTerm?: string;
    selectedImage?: string; // New prop for selected image URL
}

const NoteList: React.FC<NoteListProps> = ({ sessionId, coordinates, onJump, selectedContext, selectedTerm, selectedImage }) => {
    const { token } = useAuth();
    const [notes, setNotes] = useState<Note[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [editingNote, setEditingNote] = useState<Note | null>(null);

    // If a new image is selected and we are edit mode, maybe we don't update edit note?
    // Actually if we select an area we probably want to add a NEW note, so we should exit edit mode if it was active.
    useEffect(() => {
        if (selectedImage) {
            setEditingNote(null);
        }
    }, [selectedImage]);

    const fetchNotes = useCallback(async () => {
        setLoading(true);
        try {
            const headers: HeadersInit = {};
            if (token) headers['Authorization'] = `Bearer ${token}`;

            const res = await fetch(`/note/${sessionId}`, { headers });
            if (res.ok) {
                const data = await res.json();
                setNotes(data.notes || []);
            } else {
                setError('Failed to load notes');
            }
        } catch (e) {
            setError(String(e));
        } finally {
            setLoading(false);
        }
    }, [sessionId, token]);

    useEffect(() => {
        if (sessionId) {
            fetchNotes();
        }
    }, [sessionId, fetchNotes]);

    const handleAddNote = async (term: string, noteContent: string, coords?: { page: number, x: number, y: number }, imageUrl?: string) => {
        try {
            const headers: HeadersInit = { 'Content-Type': 'application/json' };
            if (token) headers['Authorization'] = `Bearer ${token}`;

            const res = await fetch('/note', {
                method: 'POST',
                headers,
                body: JSON.stringify({
                    session_id: sessionId,
                    term,
                    note: noteContent,
                    page_number: coords?.page,
                    x: coords?.x,
                    y: coords?.y,
                    image_url: imageUrl
                })
            });
            if (res.ok) {
                // Refresh list
                fetchNotes();
            }
        } catch (e) {
            console.error(e);
        }
    };

    const handleUpdateNote = async (id: string, term: string, noteContent: string, coords?: { page: number, x: number, y: number }, imageUrl?: string) => {
        try {
            const headers: HeadersInit = { 'Content-Type': 'application/json' };
            if (token) headers['Authorization'] = `Bearer ${token}`;

            const res = await fetch(`/note/${id}`, {
                method: 'PUT',
                headers,
                body: JSON.stringify({
                    session_id: sessionId,
                    term,
                    note: noteContent,
                    page_number: coords?.page,
                    x: coords?.x,
                    y: coords?.y,
                    image_url: imageUrl
                })
            });

            if (res.ok) {
                fetchNotes();
                setEditingNote(null);
            }
        } catch (e) {
            console.error(e);
        }
    };

    const handleDeleteNote = async (id: string) => {
        try {
            const headers: HeadersInit = {};
            if (token) headers['Authorization'] = `Bearer ${token}`;

            await fetch(`/note/${id}`, { method: 'DELETE', headers });
            setNotes(prev => prev.filter(n => n.note_id !== id));
        } catch (e) {
            console.error(e);
        }
    };

    return (
        <div className="flex flex-col h-full p-4 overflow-hidden">
            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-4">My Notes</h3>

            {error && <div className="text-xs text-red-500 mb-2">{error}</div>}

            <AddNoteForm
                onAdd={handleAddNote}
                onUpdate={handleUpdateNote}
                onCancelEdit={() => setEditingNote(null)}
                coordinates={coordinates}
                initialContent={selectedContext}
                initialTerm={selectedTerm}
                initialImage={selectedImage}
                editingNote={editingNote ? {
                    id: editingNote.note_id,
                    term: editingNote.term,
                    note: editingNote.note,
                    page_number: editingNote.page_number,
                    x: editingNote.x,
                    y: editingNote.y,
                    image_url: editingNote.image_url
                } : null}
            />

            <div className="flex-1 overflow-y-auto space-y-2 pr-1 custom-scrollbar">
                {loading && notes.length === 0 && (
                    <div className="text-center py-8 text-slate-400 text-xs">Loading notes...</div>
                )}

                {!loading && notes.length === 0 && (
                    <div className="text-center py-8 text-slate-300 text-xs border-2 border-dashed border-slate-100 rounded-xl">
                        No notes yet. <br /> Add one above!
                    </div>
                )}

                {notes.map(note => (
                    <NoteItem key={note.note_id} note={note} onDelete={handleDeleteNote} onJump={onJump} />
                ))}
            </div>
        </div>
    );
};

export default NoteList;

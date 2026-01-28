import React, { createContext, useContext, useEffect, useState } from 'react';
import { User, signInWithPopup, signOut as firebaseSignOut, onAuthStateChanged } from 'firebase/auth';
import { auth, googleProvider } from '../lib/firebase';

interface AuthContextType {
    user: User | null;
    loading: boolean;
    signInWithGoogle: () => Promise<void>;
    signInWithGithub: () => Promise<void>;
    loginAsGuest: () => void;
    logout: () => Promise<void>;
    token: string | null;
    isGuest: boolean;
}

const AuthContext = createContext<AuthContextType | null>(null);

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (!context) throw new Error('useAuth must be used within an AuthProvider');
    return context;
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [user, setUser] = useState<User | null>(null);
    const [loading, setLoading] = useState(true);
    const [token, setToken] = useState<string | null>(null);
    const [isGuest, setIsGuest] = useState(false);

    useEffect(() => {
        const unsubscribe = onAuthStateChanged(auth, async (currentUser) => {
            if (currentUser) {
                try {
                    const idToken = await currentUser.getIdToken();
                    setToken(idToken);
                    setIsGuest(false);

                    // Sync with backend - ensure user exists in DB
                    // We don't block the UI update on this, but we log errors
                    await fetch('/auth/register', {
                        method: 'POST',
                        headers: {
                            'Authorization': `Bearer ${idToken}`,
                            'Content-Type': 'application/json'
                        }
                    });
                } catch (error) {
                    console.error("Failed to sync user with backend:", error);
                    // If backend sync fails, we might still want to let them be "logged in" on frontend 
                    // or force logout. For now, we'll keep them logged in but log error.
                }
            } else {
                setToken(null);
                // Guest mode might persist via local state if not explicitly logged out
            }
            setUser(currentUser);
            if (!isGuest) setLoading(false); // Only set loading false if not waiting for guest check? Actually onAuthStateChanged fires initially
            setLoading(false);
        });

        return () => unsubscribe();
    }, [isGuest]); // Re-run if isGuest changes? No, only once.

    const signInWithGoogle = async () => {
        try {
            await signInWithPopup(auth, googleProvider);
            setIsGuest(false);
        } catch (error) {
            console.error("Error signing in with Google", error);
            throw error;
        }
    };

    const signInWithGithub = async () => {
        try {
            // Need to import githubProvider from firebase
            const { githubProvider } = await import('../lib/firebase');
            await signInWithPopup(auth, githubProvider);
            setIsGuest(false);
        } catch (error) {
            console.error("Error signing in with Github", error);
            throw error;
        }
    };

    const loginAsGuest = () => {
        setIsGuest(true);
        // We can create a mock user or just rely on isGuest flag
        // For simple logic, we just set isGuest true and let the app render
    };

    const logout = async () => {
        try {
            await firebaseSignOut(auth);
            setUser(null);
            setToken(null);
            setIsGuest(false);
        } catch (error) {
            console.error("Error signing out", error);
            throw error;
        }
    };

    return (
        <AuthContext.Provider value={{ user, loading, signInWithGoogle, signInWithGithub, loginAsGuest, logout, token, isGuest }}>
            {!loading && children}
        </AuthContext.Provider>
    );
};

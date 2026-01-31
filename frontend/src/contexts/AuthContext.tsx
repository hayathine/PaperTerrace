import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { User, signInWithPopup, signOut as firebaseSignOut, onAuthStateChanged, getIdToken } from 'firebase/auth';
import { auth, googleProvider, githubProvider } from '../lib/firebase';

interface AuthContextType {
    user: User | null;
    loading: boolean;
    signInWithGoogle: () => Promise<void>;
    signInWithGithub: () => Promise<void>;
    loginAsGuest: () => void;
    logout: () => Promise<void>;
    token: string | null;
    getToken: (forceRefresh?: boolean) => Promise<string | null>;
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
    const [isGuest, setIsGuest] = useState(true);

    const syncWithBackend = useCallback(async (idToken: string) => {
        try {
            const response = await fetch('/auth/register', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${idToken}`,
                    'Content-Type': 'application/json'
                }
            });
            if (!response.ok) {
                console.warn("Backend sync returned status:", response.status);
            }
        } catch (error) {
            console.error("Failed to sync user with backend:", error);
        }
    }, []);

    const getToken = useCallback(async (forceRefresh = false): Promise<string | null> => {
        if (!auth.currentUser) return null;
        try {
            const idToken = await getIdToken(auth.currentUser, forceRefresh);
            setToken(idToken);
            return idToken;
        } catch (error) {
            console.error("Error getting token:", error);
            return null;
        }
    }, []);

    useEffect(() => {
        const unsubscribe = onAuthStateChanged(auth, async (currentUser) => {
            if (currentUser) {
                try {
                    const idToken = await currentUser.getIdToken();
                    setToken(idToken);
                    setIsGuest(false);
                    await syncWithBackend(idToken);
                } catch (error) {
                    console.error("Error in auth state change:", error);
                }
            } else {
                setToken(null);
                setIsGuest(true);
            }
            setUser(currentUser);
            setLoading(false);
        });

        // Set up token refresh interval (every 50 minutes)
        const refreshInterval = setInterval(() => {
            if (auth.currentUser) {
                getToken(true);
            }
        }, 50 * 60 * 1000);

        return () => {
            unsubscribe();
            clearInterval(refreshInterval);
        };
    }, [syncWithBackend, getToken]);

    const signInWithGoogle = async () => {
        try {
            await signInWithPopup(auth, googleProvider);
        } catch (error) {
            console.error("Error signing in with Google", error);
            throw error;
        }
    };

    const signInWithGithub = async () => {
        try {
            await signInWithPopup(auth, githubProvider);
        } catch (error) {
            console.error("Error signing in with Github", error);
            throw error;
        }
    };

    const loginAsGuest = () => {
        setIsGuest(true);
    };

    const logout = async () => {
        try {
            await firebaseSignOut(auth);
            setUser(null);
            setToken(null);
            setIsGuest(true);
        } catch (error) {
            console.error("Error signing out", error);
            throw error;
        }
    };

    return (
        <AuthContext.Provider value={{ user, loading, signInWithGoogle, signInWithGithub, loginAsGuest, logout, token, getToken, isGuest }}>
            {!loading && children}
        </AuthContext.Provider>
    );
};

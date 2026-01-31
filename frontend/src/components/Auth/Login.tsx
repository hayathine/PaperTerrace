import React, { useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';

const Login: React.FC<{ onGuestAccess: () => void }> = ({ onGuestAccess }) => {
    const { signInWithGoogle, signInWithGithub } = useAuth();
    const [loading, setLoading] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    const handleSignIn = async (provider: 'google' | 'github') => {
        setLoading(provider);
        setError(null);
        try {
            if (provider === 'google') {
                await signInWithGoogle();
            } else {
                await signInWithGithub();
            }
        } catch (err: any) {
            console.error(`Error signing in with ${provider}:`, err);
            setError(`${provider}でのログインに失敗しました。もう一度お試しください。`);
        } finally {
            setLoading(null);
        }
    };

    return (
        <div className="flex items-center justify-center p-8">
            <div className="max-w-md w-full space-y-6">
                <div className="text-center">
                    <h2 className="text-3xl font-bold text-gray-900 tracking-tight">
                        PaperTerrace
                    </h2>
                    <p className="mt-2 text-sm text-gray-500">
                        テラスで読むように、論文をカジュアルに
                    </p>
                </div>

                {error && (
                    <div className="bg-red-50 border-l-4 border-red-400 p-4 rounded animate-in fade-in slide-in-from-top-1 duration-300">
                        <div className="flex">
                            <div className="flex-shrink-0">
                                <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                                </svg>
                            </div>
                            <div className="ml-3">
                                <p className="text-sm text-red-700">{error}</p>
                            </div>
                        </div>
                    </div>
                )}

                <div className="space-y-4">
                    <button
                        onClick={() => handleSignIn('google')}
                        disabled={!!loading}
                        className="group relative w-full flex justify-center py-3 px-4 border border-transparent text-sm font-semibold rounded-xl text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 transition-all duration-200 transform hover:scale-[1.02] active:scale-[0.98] disabled:opacity-70 disabled:cursor-not-allowed"
                    >
                        {loading === 'google' ? (
                            <svg className="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                        ) : (
                            "Googleでログイン"
                        )}
                    </button>

                    <button
                        onClick={() => handleSignIn('github')}
                        disabled={!!loading}
                        className="group relative w-full flex justify-center py-3 px-4 border border-gray-300 text-sm font-semibold rounded-xl text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500 transition-all duration-200 transform hover:scale-[1.02] active:scale-[0.98] disabled:opacity-70 disabled:cursor-not-allowed"
                    >
                        {loading === 'github' ? (
                            <svg className="animate-spin h-5 w-5 text-gray-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                        ) : (
                            "GitHubでログイン"
                        )}
                    </button>

                    <div className="relative py-4">
                        <div className="absolute inset-0 flex items-center">
                            <div className="w-full border-t border-gray-100" />
                        </div>
                        <div className="relative flex justify-center text-xs">
                            <span className="px-3 bg-white text-gray-400 uppercase tracking-widest font-medium">Or</span>
                        </div>
                    </div>

                    <button
                        onClick={onGuestAccess}
                        className="group relative w-full flex justify-center py-3 px-4 border border-dashed border-gray-300 text-sm font-medium rounded-xl text-gray-500 bg-gray-50/50 hover:bg-gray-50 hover:text-gray-700 transition-all duration-200"
                    >
                        ゲストとして利用する
                    </button>
                </div>

                <p className="text-center text-[10px] text-gray-400 pt-4">
                    ログインすることで、利用規約およびプライバシーポリシーに同意したものとみなされます。
                </p>
            </div>
        </div>
    );
};

export default Login;

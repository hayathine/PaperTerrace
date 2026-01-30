import React from 'react';
import { useAuth } from '../../contexts/AuthContext';

const Login: React.FC<{ onGuestAccess: () => void }> = ({ onGuestAccess }) => {
    const { signInWithGoogle, signInWithGithub } = useAuth();

    return (
        <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
            <div className="max-w-md w-full space-y-8">
                <div>
                    <h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900">
                        PaperTerrace
                    </h2>
                    <p className="mt-2 text-center text-sm text-gray-600">
                        Sign in to access your papers
                    </p>
                </div>
                <div className="mt-8 space-y-4">
                    <button
                        onClick={signInWithGoogle}
                        className="group relative w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                    >
                        Sign in with Google
                    </button>
                    <button
                        onClick={signInWithGithub}
                        className="group relative w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-gray-800 hover:bg-gray-900 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500"
                    >
                        Sign in with GitHub
                    </button>
                    <div className="relative">
                        <div className="absolute inset-0 flex items-center">
                            <div className="w-full border-t border-gray-300" />
                        </div>
                        <div className="relative flex justify-center text-sm">
                            <span className="px-2 bg-gray-50 text-gray-500">Or continue as guest</span>
                        </div>
                    </div>
                    <button
                        onClick={onGuestAccess}
                        className="group relative w-full flex justify-center py-2 px-4 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                    >
                        Guest Access
                    </button>
                </div>
            </div>
        </div>
    );
};

export default Login;

import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { useAuth } from "../../contexts/AuthContext";

const Login: React.FC<{ onGuestAccess: () => void }> = ({ onGuestAccess }) => {
  const { t } = useTranslation();
  const {
    signInWithGoogle,
    signInWithGithub,
    signInWithGoogleRedirect,
    signInWithGithubRedirect,
  } = useAuth();
  const [loading, setLoading] = useState<string | null>(null);

  const [error, setError] = useState<string | null>(null);

  const handleSignIn = async (
    provider: "google" | "github",
    method: "popup" | "redirect" = "popup",
  ) => {
    setLoading(provider);
    setError(null);
    try {
      if (provider === "google") {
        if (method === "popup") await signInWithGoogle();
        else await signInWithGoogleRedirect();
      } else {
        if (method === "popup") await signInWithGithub();
        else await signInWithGithubRedirect();
      }
    } catch (err: any) {
      console.error(`Error signing in with ${provider} (${method}):`, err);
      const errorCode = err.code || "unknown";
      const errorMessage = err.message || "Error occurred";
      setError(
        `${provider}でのログインに失敗しました。 (${errorCode}: ${errorMessage})`,
      );
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
          <p className="mt-2 text-sm text-gray-500">{t("auth.tagline")}</p>
        </div>

        {error && (
          <div className="bg-red-50 border-l-4 border-red-400 p-4 rounded animate-in fade-in slide-in-from-top-1 duration-300">
            <div className="flex">
              <div className="flex-shrink-0">
                <svg
                  className="h-5 w-5 text-red-400"
                  viewBox="0 0 20 20"
                  fill="currentColor"
                >
                  <path
                    fillRule="evenodd"
                    d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                    clipRule="evenodd"
                  />
                </svg>
              </div>
              <div className="ml-3">
                <p className="text-sm text-red-700">{error}</p>
              </div>
            </div>
          </div>
        )}

        <div className="space-y-4">
          <div className="flex flex-col gap-2">
            <button
              onClick={() => handleSignIn("google", "popup")}
              disabled={!!loading}
              className="group relative w-full flex justify-center py-2.5 px-4 border border-transparent text-sm font-semibold rounded-xl text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none transition-all disabled:opacity-70"
            >
              {loading === "google"
                ? t("auth.signing_in")
                : t("auth.login_google")}
            </button>

            <button
              onClick={() => handleSignIn("github", "popup")}
              disabled={!!loading}
              className="group relative w-full flex justify-center py-2.5 px-4 border border-gray-300 text-sm font-semibold rounded-xl text-gray-700 bg-white hover:bg-gray-50 focus:outline-none transition-all disabled:opacity-70"
            >
              {loading === "github"
                ? t("auth.signing_in")
                : t("auth.login_github")}
            </button>
          </div>

          <div className="pt-2">
            <p className="text-[10px] text-gray-400 text-center mb-2">
              {t("auth.login_redirect_hint")}
            </p>

            <div className="flex gap-2">
              <button
                onClick={() => handleSignIn("google", "redirect")}
                className="flex-1 py-1.5 px-2 border border-black/10 rounded-lg text-[10px] text-gray-500 hover:bg-gray-50 transition-colors"
              >
                Google (Redirect)
              </button>
              <button
                onClick={() => handleSignIn("github", "redirect")}
                className="flex-1 py-1.5 px-2 border border-black/10 rounded-lg text-[10px] text-gray-500 hover:bg-gray-50 transition-colors"
              >
                GitHub (Redirect)
              </button>
            </div>
          </div>

          <div className="relative py-4">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-gray-100" />
            </div>
            <div className="relative flex justify-center text-xs">
              <span className="px-3 bg-white text-gray-400 uppercase tracking-widest font-medium">
                Or
              </span>
            </div>
          </div>

          <button
            onClick={onGuestAccess}
            className="group relative w-full flex justify-center py-3 px-4 border border-dashed border-gray-300 text-sm font-medium rounded-xl text-gray-500 bg-gray-50/50 hover:bg-gray-50 hover:text-gray-700 transition-all duration-200"
          >
            {t("auth.guest_access")}
          </button>
        </div>

        <p className="text-center text-[10px] text-gray-400 pt-4">
          {t("auth.terms_agreement")}
        </p>
      </div>
    </div>
  );
};

export default Login;

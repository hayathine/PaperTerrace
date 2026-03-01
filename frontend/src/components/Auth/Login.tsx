import type React from "react";
import { useState } from "react";
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
		<div className="flex flex-col w-full relative">
			{/* Decorative background element */}
			<div className="absolute top-0 left-0 w-full h-32 bg-gradient-to-br from-orange-600 to-amber-700 opacity-[0.03]" />

			<div className="px-8 pt-10 pb-12 relative z-10">
				<div className="text-center mb-10">
					<div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-tr from-orange-600 to-amber-500 rounded-2xl shadow-lg shadow-orange-200 mb-4 animate-in zoom-in duration-500">
						<svg
							className="w-8 h-8 text-white"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
						>
							<path
								strokeLinecap="round"
								strokeLinejoin="round"
								strokeWidth="2"
								d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
							/>
						</svg>
					</div>
					<h2 className="text-4xl font-black text-slate-800 tracking-tight mb-2">
						Paper<span className="text-orange-600">Terrace</span>
					</h2>
					<p className="text-slate-500 font-medium">{t("auth.tagline")}</p>
				</div>

				{error && (
					<div className="mb-6 bg-red-50 border border-red-100 p-4 rounded-xl animate-in fade-in slide-in-from-top-2 duration-300">
						<div className="flex">
							<div className="flex-shrink-0">
								<svg
									className="h-5 w-5 text-red-500"
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
								<p className="text-sm text-red-700 font-medium">{error}</p>
							</div>
						</div>
					</div>
				)}

				<div className="space-y-4">
					<div className="grid grid-cols-1 gap-3">
						<button
							type="button"
							onClick={() => handleSignIn("google", "popup")}
							disabled={!!loading}
							className="group relative w-full flex items-center justify-center py-3.5 px-4 border border-transparent text-sm font-bold rounded-xl text-white bg-orange-600 hover:bg-orange-700 active:scale-[0.98] focus:outline-none transition-all shadow-md shadow-orange-100 disabled:opacity-70"
						>
							<div className="flex items-center gap-2">
								{loading === "google" ? (
									<svg
										className="animate-spin h-5 w-5 text-white"
										xmlns="http://www.w3.org/2000/svg"
										fill="none"
										viewBox="0 0 24 24"
									>
										<circle
											className="opacity-25"
											cx="12"
											cy="12"
											r="10"
											stroke="currentColor"
											strokeWidth="4"
										></circle>
										<path
											className="opacity-75"
											fill="currentColor"
											d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
										></path>
									</svg>
								) : (
									<svg
										className="w-5 h-5"
										viewBox="0 0 24 24"
										fill="currentColor"
									>
										<path d="M12.48 10.92v3.28h7.84c-.24 1.84-.908 3.152-1.928 4.176-1.232 1.232-3.156 2.508-6.192 2.508-4.832 0-8.62-3.908-8.62-8.74s3.788-8.74 8.62-8.74c2.592 0 5.168.996 6.944 2.768l2.312-2.312C18.948 1.412 15.936 0 12.48 0 5.832 0 0 5.368 0 12s5.832 12 12.48 12c3.552 0 6.228-1.172 8.328-3.288 2.152-2.152 2.828-5.18 2.828-7.624 0-.748-.068-1.464-.176-2.176H12.48z" />
									</svg>
								)}
								<span>
									{loading === "google"
										? t("auth.signing_in")
										: t("auth.google")}
								</span>
							</div>
						</button>

						<button
							type="button"
							onClick={() => handleSignIn("github", "popup")}
							disabled={!!loading}
							className="group relative w-full flex items-center justify-center py-3.5 px-4 border border-slate-200 text-sm font-bold rounded-xl text-slate-700 bg-white hover:bg-slate-50 active:scale-[0.98] focus:outline-none transition-all shadow-sm disabled:opacity-70"
						>
							<div className="flex items-center gap-2">
								{loading === "github" ? (
									<svg
										className="animate-spin h-5 w-5 text-orange-600"
										xmlns="http://www.w3.org/2000/svg"
										fill="none"
										viewBox="0 0 24 24"
									>
										<circle
											className="opacity-25"
											cx="12"
											cy="12"
											r="10"
											stroke="currentColor"
											strokeWidth="4"
										></circle>
										<path
											className="opacity-75"
											fill="currentColor"
											d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
										></path>
									</svg>
								) : (
									<svg
										className="w-5 h-5"
										fill="currentColor"
										viewBox="0 0 24 24"
									>
										<path
											fillRule="evenodd"
											d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"
											clipRule="evenodd"
										/>
									</svg>
								)}
								<span>
									{loading === "github"
										? t("auth.signing_in")
										: t("auth.github")}
								</span>
							</div>
						</button>
					</div>

					<div className="py-4">
						<div className="flex items-center gap-4 mb-4">
							<div className="h-px w-full bg-slate-100" />
							<span className="text-[10px] text-slate-400 font-bold uppercase tracking-[0.2em] whitespace-nowrap">
								{t("auth.redirect_hint")}
							</span>
							<div className="h-px w-full bg-slate-100" />
						</div>

						<div className="grid grid-cols-2 gap-3">
							<button
								type="button"
								onClick={() => handleSignIn("google", "redirect")}
								className="py-2.5 px-3 border border-slate-100 rounded-xl text-xs font-semibold text-slate-500 hover:bg-slate-50 active:scale-[0.98] transition-all"
							>
								Google
							</button>
							<button
								type="button"
								onClick={() => handleSignIn("github", "redirect")}
								className="py-2.5 px-3 border border-slate-100 rounded-xl text-xs font-semibold text-slate-500 hover:bg-slate-50 active:scale-[0.98] transition-all"
							>
								GitHub
							</button>
						</div>
					</div>

					<div className="relative py-4">
						<div className="absolute inset-0 flex items-center">
							<div className="w-full border-t border-slate-100" />
						</div>
						<div className="relative flex justify-center text-[10px]">
							<span className="px-4 bg-white text-slate-300 font-black uppercase tracking-[0.3em]">
								Or
							</span>
						</div>
					</div>

					<button
						type="button"
						onClick={onGuestAccess}
						className="group relative w-full flex items-center justify-center py-4 px-4 border-2 border-dashed border-slate-200 text-sm font-bold rounded-2xl text-slate-500 bg-slate-50/30 hover:bg-orange-50 hover:text-orange-600 hover:border-orange-100 transition-all duration-300"
					>
						<span className="flex items-center gap-2">
							<svg
								className="w-5 h-5"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
							>
								<path
									strokeLinecap="round"
									strokeLinejoin="round"
									strokeWidth="2"
									d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
								/>
							</svg>
							{t("auth.guest")}
						</span>
					</button>

					<p className="text-center text-[10px] text-slate-400 font-medium leading-relaxed px-4 mt-8">
						{t("auth.terms_hint")}
					</p>
				</div>
			</div>
		</div>
	);
};

export default Login;

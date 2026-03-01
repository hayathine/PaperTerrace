import type React from "react";
import { useState } from "react";

type SubmitStatus = "idle" | "submitting" | "submitted" | "error";

const RequestForm: React.FC = () => {
	const [name, setName] = useState("");
	const [email, setEmail] = useState("");
	const [message, setMessage] = useState("");
	const [status, setStatus] = useState<SubmitStatus>("idle");

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		if (!name.trim() || !email.trim() || !message.trim()) return;

		setStatus("submitting");
		try {
			const res = await fetch("/api/contact", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ name, email, message }),
			});
			if (!res.ok) throw new Error("server error");

			setStatus("submitted");
			setName("");
			setEmail("");
			setMessage("");
		} catch {
			setStatus("error");
		}
	};

	return (
		<div className="w-full max-w-2xl mt-12 animate-fade-in-up">
			<div className="relative bg-white/70 backdrop-blur-sm border border-slate-200 rounded-3xl p-8 shadow-lg shadow-slate-100/50">
				{/* ヘッダー */}
				<div className="mb-6">
					<span className="inline-block px-3 py-1 bg-orange-50 text-orange-500 text-xs font-bold uppercase tracking-widest rounded-full border border-orange-100 mb-3">
						Feature Request
					</span>
					<h2 className="text-xl font-bold text-slate-800">
						要望・ご意見を送る
					</h2>
					<p className="mt-1 text-sm text-slate-500">
						機能への要望やフィードバックをお気軽にどうぞ。
					</p>
				</div>

				{status === "submitted" ? (
					<div className="flex flex-col items-center justify-center py-8 space-y-3">
						<div className="w-12 h-12 rounded-full bg-emerald-50 flex items-center justify-center">
							<svg
								className="w-6 h-6 text-emerald-500"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
							>
								<path
									strokeLinecap="round"
									strokeLinejoin="round"
									strokeWidth={2}
									d="M5 13l4 4L19 7"
								/>
							</svg>
						</div>
						<p className="text-sm font-bold text-slate-700">
							ありがとうございます！
						</p>
						<p className="text-xs text-slate-500">要望を受け付けました。</p>
						<button
							type="button"
							onClick={() => setStatus("idle")}
							className="mt-2 text-xs text-orange-500 hover:underline"
						>
							もう一件送る
						</button>
					</div>
				) : (
					<form onSubmit={handleSubmit} className="space-y-4">
						<div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
							<div>
								<label
									htmlFor="req-name"
									className="block text-xs font-semibold text-slate-500 mb-1"
								>
									お名前
								</label>
								<input
									id="req-name"
									type="text"
									required
									value={name}
									onChange={(e) => setName(e.target.value)}
									placeholder="Terrace Taro"
									className="w-full px-4 py-2.5 text-sm bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-300 focus:border-transparent transition-all"
								/>
							</div>
							<div>
								<label
									htmlFor="req-email"
									className="block text-xs font-semibold text-slate-500 mb-1"
								>
									メールアドレス
								</label>
								<input
									id="req-email"
									type="email"
									required
									value={email}
									onChange={(e) => setEmail(e.target.value)}
									placeholder="you@example.com"
									className="w-full px-4 py-2.5 text-sm bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-300 focus:border-transparent transition-all"
								/>
							</div>
						</div>

						<div>
							<label
								htmlFor="req-message"
								className="block text-xs font-semibold text-slate-500 mb-1"
							>
								メッセージ
							</label>
							<textarea
								id="req-message"
								required
								value={message}
								onChange={(e) => setMessage(e.target.value)}
								rows={4}
								placeholder="こんな機能があると嬉しい、など何でも..."
								className="w-full px-4 py-2.5 text-sm bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-300 focus:border-transparent transition-all resize-none"
							/>
						</div>

						{status === "error" && (
							<p className="text-xs text-rose-500 font-medium">
								送信に失敗しました。時間をおいて再度お試しください。
							</p>
						)}

						<div className="flex justify-end">
							<button
								type="submit"
								disabled={
									status === "submitting" ||
									!name.trim() ||
									!email.trim() ||
									!message.trim()
								}
								className="flex items-center gap-2 px-6 py-2.5 bg-gradient-to-r from-orange-500 to-amber-500 hover:from-orange-400 hover:to-amber-400 disabled:from-slate-300 disabled:to-slate-300 text-white text-sm font-bold rounded-xl shadow-md shadow-orange-200/50 transition-all duration-200 active:scale-95 disabled:active:scale-100"
							>
								{status === "submitting" ? (
									<>
										<div className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
										<span>送信中...</span>
									</>
								) : (
									<>
										<svg
											className="w-4 h-4"
											fill="none"
											stroke="currentColor"
											viewBox="0 0 24 24"
										>
											<path
												strokeLinecap="round"
												strokeLinejoin="round"
												strokeWidth={2}
												d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
											/>
										</svg>
										<span>送信する</span>
									</>
								)}
							</button>
						</div>
					</form>
				)}
			</div>
		</div>
	);
};

export default RequestForm;

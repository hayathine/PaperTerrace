import type React from "react";
import { useState } from "react";
import { API_URL } from "@/config";

type SubmitStatus = "idle" | "submitting" | "submitted" | "error";

const RequestForm: React.FC = () => {
	const [message, setMessage] = useState("");
	const [status, setStatus] = useState<SubmitStatus>("idle");

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		if (!message.trim()) return;

		setStatus("submitting");
		try {
			const res = await fetch(`${API_URL}/api/contact`, {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ message }),
			});
			if (!res.ok) throw new Error("server error");

			setStatus("submitted");
			setMessage("");
		} catch {
			setStatus("error");
		}
	};

	return (
		<div className="w-full max-w-sm mt-4 animate-fade-in-up">
			<div className="relative bg-white/70 backdrop-blur-sm border border-slate-200 rounded-xl p-3 shadow-md shadow-slate-100/50">
				{/* ヘッダー */}
				<div className="mb-2 flex items-center justify-between">
					<div>
						<h2 className="text-[13px] font-bold text-slate-800 leading-tight">
							要望・ご意見を送る
						</h2>
					</div>
					<span className="px-1.5 py-0.5 bg-orange-50 text-orange-500 text-[9px] font-black uppercase tracking-wider rounded border border-orange-100">
						Feedback
					</span>
				</div>

				{status === "submitted" ? (
					<div className="flex flex-col items-center justify-center py-3 space-y-1">
						<p className="text-xs font-bold text-slate-700">
							ありがとうございます！
						</p>
						<button
							type="button"
							onClick={() => setStatus("idle")}
							className="text-[10px] text-orange-500 hover:underline"
						>
							もう一度
						</button>
					</div>
				) : (
					<form onSubmit={handleSubmit} className="space-y-2">
						<textarea
							id="req-message"
							required
							value={message}
							onChange={(e) => setMessage(e.target.value)}
							rows={2}
							placeholder="機能要望やご意見をお気軽にどうぞ..."
							className="w-full px-2.5 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-orange-300 focus:border-transparent transition-all resize-none"
						/>

						{status === "error" && (
							<p className="text-[10px] text-rose-500 font-medium">
								送信に失敗しました。再試行してください。
							</p>
						)}

						<div className="flex justify-end pt-0.5">
							<button
								type="submit"
								disabled={status === "submitting" || !message.trim()}
								className="flex items-center gap-1.5 px-3 py-1.5 bg-gradient-to-r from-orange-500 to-amber-500 hover:from-orange-400 hover:to-amber-400 disabled:from-slate-300 disabled:to-slate-300 text-white text-[11px] font-bold rounded-lg shadow-sm transition-all duration-200 active:scale-95"
							>
								{status === "submitting" ? (
									<>
										<div className="w-3 h-3 border-2 border-white/40 border-t-white rounded-full animate-spin" />
										<span>送信中</span>
									</>
								) : (
									<>
										<svg
											className="w-3.5 h-3.5"
											fill="none"
											stroke="currentColor"
											viewBox="0 0 24 24"
										>
											<path
												strokeLinecap="round"
												strokeLinejoin="round"
												strokeWidth={2.5}
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

import type React from "react";
import { useTranslation } from "react-i18next";

interface ServiceOutageProps {
	isMaintenance?: boolean;
	message?: string;
}

const ServiceOutage: React.FC<ServiceOutageProps> = ({
	isMaintenance = false,
	message,
}) => {
	const { t } = useTranslation();

	return (
		<div
			data-testid="service-outage"
			className="fixed inset-0 z-[10000] flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xl transition-all duration-700"
		>
			<div className="relative max-w-lg w-full overflow-hidden bg-white/80 backdrop-blur-md rounded-[2.5rem] shadow-[0_32px_128px_-16px_rgba(0,0,0,0.3)] border border-white/50 animate-in fade-in zoom-in-95 duration-500 flex flex-col items-center text-center p-12">
				{/* Aesthetic Background Shapes */}
				<div className="absolute top-0 right-0 -mr-20 -mt-20 w-64 h-64 bg-orange-100 rounded-full mix-blend-multiply filter blur-3xl opacity-30 animate-pulse"></div>
				<div className="absolute bottom-0 left-0 -ml-20 -mb-20 w-64 h-64 bg-amber-100 rounded-full mix-blend-multiply filter blur-3xl opacity-30 animate-pulse [animation-delay:1s]"></div>

				<div className="relative mb-8">
					<div className="w-24 h-24 rounded-3xl bg-gradient-to-tr from-orange-500 to-amber-400 flex items-center justify-center shadow-2xl shadow-orange-500/20 rotate-12 transition-transform hover:rotate-3 duration-500 transform-gpu">
						{isMaintenance ? (
							<svg
								className="w-12 h-12 text-white"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
							>
								<path
									strokeLinecap="round"
									strokeLinejoin="round"
									strokeWidth="1.5"
									d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
								/>
								<path
									strokeLinecap="round"
									strokeLinejoin="round"
									strokeWidth="1.5"
									d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
								/>
							</svg>
						) : (
							<svg
								className="w-12 h-12 text-white"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
							>
								<path
									strokeLinecap="round"
									strokeLinejoin="round"
									strokeWidth="1.5"
									d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
								/>
							</svg>
						)}
					</div>
					<div className="absolute -top-1 -right-1 flex h-6 w-6">
						<span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-orange-400 opacity-75"></span>
						<span className="relative inline-flex rounded-full h-6 w-6 bg-orange-500 border-4 border-white"></span>
					</div>
				</div>

				<h1 className="text-3xl font-black text-slate-800 mb-4 tracking-tight">
					{isMaintenance
						? t("outage.maintenance_title", "System Maintenance")
						: t("outage.outage_title", "Service Temporarily Unavailable")}
				</h1>

				<p className="text-lg text-slate-600 font-medium leading-relaxed mb-10 max-w-sm">
					{message ||
						(isMaintenance
							? t(
									"outage.maintenance_message",
									"We're currently performing some improvements. We'll be back shortly.",
								)
							: t(
									"outage.outage_message",
									"Our servers are currently over capacity. Please try again in a few minutes.",
								))}
				</p>

				<div className="flex flex-col gap-4 w-full">
					<button
						type="button"
						onClick={() => window.location.reload()}
						className="group relative w-full py-4 px-6 bg-slate-900 hover:bg-slate-800 text-white rounded-2xl font-bold transition-all duration-300 shadow-xl shadow-slate-900/20 active:scale-[0.98] overflow-hidden"
					>
						<span className="relative z-10 flex items-center justify-center gap-2">
							<svg
								className="w-5 h-5 transition-transform group-hover:rotate-180 duration-500"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
							>
								<path
									strokeLinecap="round"
									strokeLinejoin="round"
									strokeWidth="2"
									d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
								/>
							</svg>
							{t("outage.retry_button", "Retry Connection")}
						</span>
						<div className="absolute inset-0 bg-gradient-to-tr from-white/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity"></div>
					</button>

					<p className="text-[11px] text-slate-400 font-bold uppercase tracking-[0.2em] mt-4 flex items-center justify-center gap-2">
						<span className="w-1.5 h-1.5 rounded-full bg-slate-200 animate-pulse"></span>
						Auto-refreshing status
						<span className="w-1.5 h-1.5 rounded-full bg-slate-200 animate-pulse [animation-delay:0.3s]"></span>
					</p>
				</div>
			</div>
		</div>
	);
};

export default ServiceOutage;

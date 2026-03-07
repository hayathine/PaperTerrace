import { Component, type ErrorInfo, type ReactNode } from "react";
import { createLogger } from "@/lib/logger";

const log = createLogger("ErrorBoundary");

interface Props {
	children: ReactNode;
}

interface State {
	hasError: boolean;
}

class ErrorBoundary extends Component<Props, State> {
	public state: State = {
		hasError: false,
	};

	public static getDerivedStateFromError(_error: Error): State {
		return { hasError: true };
	}

	public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
		log.error("component_did_catch", error.message, { error, errorInfo });
	}

	public render() {
		if (this.state.hasError) {
			return (
				<div className="flex flex-col items-center justify-center min-h-[300px] p-10 m-10 bg-stone-50 border border-stone-200 rounded-xl text-center">
					<div className="text-4xl mb-4">🌿</div>
					<h2 className="text-xl font-semibold text-stone-700 mb-2">
						予期しないエラーが発生しました
					</h2>
					<p className="text-stone-500 text-sm mb-6 max-w-sm">
						問題が報告されました。ページを再読み込みするか、しばらく時間をおいてからお試しください。
					</p>
					<button
						type="button"
						onClick={() => window.location.reload()}
						className="px-5 py-2 bg-stone-700 text-white text-sm rounded-lg hover:bg-stone-800 transition-colors"
					>
						ページを再読み込み
					</button>
				</div>
			);
		}

		return this.props.children;
	}
}

export default ErrorBoundary;

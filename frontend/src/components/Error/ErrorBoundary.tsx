import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
	children: ReactNode;
}

interface State {
	hasError: boolean;
	error: Error | null;
}

class ErrorBoundary extends Component<Props, State> {
	public state: State = {
		hasError: false,
		error: null,
	};

	public static getDerivedStateFromError(error: Error): State {
		return { hasError: true, error };
	}

	public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
		console.error("Uncaught error:", error, errorInfo);
	}

	public render() {
		if (this.state.hasError) {
			return (
				<div className="p-10 bg-red-50 border-2 border-red-200 rounded-xl m-10">
					<h2 className="text-2xl font-bold text-red-700 mb-4">
						Something went wrong.
					</h2>
					<pre className="p-4 bg-white border border-red-100 rounded text-red-600 overflow-auto max-h-96">
						{this.state.error?.stack}
					</pre>
					<button
						type="button"
						onClick={() => window.location.reload()}
						className="mt-6 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 transition-colors"
					>
						Reload Page
					</button>
				</div>
			);
		}

		return this.props.children;
	}
}

export default ErrorBoundary;

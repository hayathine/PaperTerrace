import { API_URL } from "@/config";

type LogLevel = "debug" | "info" | "warn" | "error";

const LOG_LEVELS: Record<LogLevel, number> = {
	debug: 0,
	info: 1,
	warn: 2,
	error: 3,
};

// 本番: warn以上のみ, 開発: debug以上すべて
const CURRENT_LEVEL: LogLevel = import.meta.env.PROD ? "warn" : "debug";

async function reportErrorToServer(
	component: string,
	operation: string,
	message: string,
	ctx?: object,
): Promise<void> {
	try {
		const errorObj =
			ctx && "error" in ctx ? (ctx as { error: unknown }).error : undefined;
		const isError = errorObj instanceof Error;

		await fetch(`${API_URL}/api/client-errors`, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			credentials: "include",
			body: JSON.stringify({
				message,
				component,
				operation,
				error_name: isError ? errorObj.name : undefined,
				stack: isError ? errorObj.stack : undefined,
				context: ctx,
				url: typeof window !== "undefined" ? window.location.href : undefined,
			}),
		});
	} catch {
		// サーバー送信失敗はサイレントに無視する（無限ループ回避）
	}
}

export function createLogger(component: string) {
	const log = (
		level: LogLevel,
		operation: string,
		message: string,
		ctx?: object,
	) => {
		if (LOG_LEVELS[level] < LOG_LEVELS[CURRENT_LEVEL]) return;
		const prefix = `[${component}.${operation}]`;
		const args = ctx ? [prefix, message, ctx] : [prefix, message];
		(console as unknown as Record<string, (...a: unknown[]) => void>)[level](
			...args,
		);

		if (level === "error") {
			reportErrorToServer(component, operation, message, ctx);
		}
	};

	return {
		debug: (op: string, msg: string, ctx?: object) =>
			log("debug", op, msg, ctx),
		info: (op: string, msg: string, ctx?: object) => log("info", op, msg, ctx),
		warn: (op: string, msg: string, ctx?: object) => log("warn", op, msg, ctx),
		error: (op: string, msg: string, ctx?: object) =>
			log("error", op, msg, ctx),
	};
}

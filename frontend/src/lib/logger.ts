type LogLevel = "debug" | "info" | "warn" | "error";

const LOG_LEVELS: Record<LogLevel, number> = {
	debug: 0,
	info: 1,
	warn: 2,
	error: 3,
};

// 本番: warn以上のみ, 開発: debug以上すべて
const CURRENT_LEVEL: LogLevel = import.meta.env.PROD ? "warn" : "debug";

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
		// console[level] may not be typed as expected if level is dynamic string in some environments
		// But in modern TS/Browser it's fine.
		(console as any)[level](...args);
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

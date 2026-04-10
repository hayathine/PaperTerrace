import { useEffect, useRef } from "react";
import { API_URL } from "@/config";
import { createLogger } from "@/lib/logger";
import { syncTrajectory } from "../lib/recommendation";

const log = createLogger("usePaperLifecycle");

/**
 * 論文ライフサイクル管理フック。
 * 論文切り替え時の Context Cache 削除とセッション時間トラッキングを担う。
 */
export function usePaperLifecycle(
	currentPaperId: string | null,
	sessionId: string,
	token: string | null,
) {
	const prevPaperIdRef = useRef<string | null>(null);
	const paperStartTimeRef = useRef<number | null>(null);

	const deleteCache = (paperId: string) => {
		const formData = new FormData();
		formData.append("session_id", sessionId);
		formData.append("paper_id", paperId);

		if (navigator.sendBeacon) {
			navigator.sendBeacon(`${API_URL}/api/chat/cache/delete`, formData);
		} else {
			fetch(`${API_URL}/api/chat/cache/delete`, {
				method: "POST",
				body: formData,
				keepalive: true,
			}).catch((e) =>
				log.error("delete_cache", "Failed to delete cache", { error: e }),
			);
		}
	};

	const sendDurationTrace = (paperId: string) => {
		if (paperStartTimeRef.current) {
			const duration = (Date.now() - paperStartTimeRef.current) / 1000;
			syncTrajectory(
				{
					session_id: sessionId,
					paper_id: paperId,
					session_duration: duration,
				},
				token,
			);
		}
	};

	// 論文切り替え時: 旧論文のキャッシュ削除 & 時間記録
	useEffect(() => {
		if (prevPaperIdRef.current && prevPaperIdRef.current !== currentPaperId) {
			sendDurationTrace(prevPaperIdRef.current);
			deleteCache(prevPaperIdRef.current);
		}

		if (currentPaperId && prevPaperIdRef.current !== currentPaperId) {
			paperStartTimeRef.current = Date.now();
		} else if (!currentPaperId) {
			paperStartTimeRef.current = null;
		}

		prevPaperIdRef.current = currentPaperId;
	}, [currentPaperId, sessionId, token]);

	// ページ離脱時: キャッシュ削除 & 時間送信
	useEffect(() => {
		const handleBeforeUnload = () => {
			if (!currentPaperId) return;

			if (paperStartTimeRef.current) {
				const duration = (Date.now() - paperStartTimeRef.current) / 1000;
				syncTrajectory(
					{
						session_id: sessionId,
						paper_id: currentPaperId,
						session_duration: duration,
					},
					token,
				);
			}

			const formData = new FormData();
			formData.append("session_id", sessionId);
			formData.append("paper_id", currentPaperId);
			navigator.sendBeacon(`${API_URL}/api/chat/cache/delete`, formData);
		};

		window.addEventListener("beforeunload", handleBeforeUnload);
		return () => window.removeEventListener("beforeunload", handleBeforeUnload);
	}, [currentPaperId, sessionId, token]);
}

import { useEffect, useState } from "react";
import { createLogger } from "@/lib/logger";
import { db, isDbAvailable } from "./index";

const log = createLogger("DBSync");

export function useSyncStatus() {
	const [status, setStatus] = useState<"synced" | "pending" | "offline">(
		"synced",
	);
	const [isOnline, setIsOnline] = useState(navigator.onLine);

	useEffect(() => {
		const handleOnline = () => setIsOnline(true);
		const handleOffline = () => setIsOnline(false);

		window.addEventListener("online", handleOnline);
		window.addEventListener("offline", handleOffline);

		return () => {
			window.removeEventListener("online", handleOnline);
			window.removeEventListener("offline", handleOffline);
		};
	}, []);

	useEffect(() => {
		if (!isOnline) {
			setStatus("offline");
			return;
		}

		if (!isDbAvailable()) {
			setStatus("synced");
			return;
		}

		// Check for unsynced changes
		const checkSync = async () => {
			try {
				const unsyncedCount = await db.edit_history
					.where("synced")
					.equals(0)
					.count();
				setStatus(unsyncedCount > 0 ? "pending" : "synced");
			} catch (e) {
				log.warn("check_sync", "Failed to check sync status", { error: e });

				setStatus("synced");
			}
		};

		const interval = setInterval(checkSync, 5000);
		checkSync();

		return () => clearInterval(interval);
	}, [isOnline]);

	return status;
}

export async function recordEdit(
	paper_id: string,
	type: "note" | "stamp",
	data: any,
) {
	if (!isDbAvailable()) return;
	try {
		await db.edit_history.add({
			paper_id,
			type,
			data,
			synced: false,
			created_at: Date.now(),
		});
	} catch (e) {
		log.error("record_edit", "Failed to record edit", { error: e });
	}
}

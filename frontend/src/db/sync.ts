import { db } from "./index";
import { useEffect, useState } from "react";

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

    // Check for unsynced changes
    const checkSync = async () => {
      const unsyncedCount = await db.edit_history
        .where("synced")
        .equals(0)
        .count();
      setStatus(unsyncedCount > 0 ? "pending" : "synced");
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
  await db.edit_history.add({
    paper_id,
    type,
    data,
    synced: false,
    created_at: Date.now(),
  });
}

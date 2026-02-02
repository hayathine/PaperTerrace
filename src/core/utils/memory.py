import asyncio
import logging
import os

logger = logging.getLogger("app_logger")


def get_available_memory_mb() -> float:
    """
    システムの利用可能なメモリ（MB）を返却する。
    """
    try:
        if not os.path.exists("/proc/meminfo"):
            return 0.0
        with open("/proc/meminfo", "r") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    avail_kb = int(line.split(":")[1].strip().split()[0])
                    return avail_kb / 1024.0
    except Exception:
        pass
    return 0.0


def get_total_memory_mb() -> float:
    """
    システムの全メモリ（MB）を返却する。
    """
    try:
        if not os.path.exists("/proc/meminfo"):
            return 1.0
        with open("/proc/meminfo", "r") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    total_kb = int(line.split(":")[1].strip().split()[0])
                    return total_kb / 1024.0
    except Exception:
        pass
    return 1.0


def log_memory(label: str):
    """
    システムのメモリ使用状況をログに出力する。
    """
    try:
        rss_mb = 0.0
        if os.path.exists("/proc/self/status"):
            with open("/proc/self/status", "r") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        rss_kb = int(line.split(":")[1].strip().split()[0])
                        rss_mb = rss_kb / 1024.0
                        break

        avail_mb = get_available_memory_mb()
        total_mb = get_total_memory_mb()
        usage_pct = (1.0 - (avail_mb / total_mb)) * 100.0 if total_mb > 0 else 0

        logger.info(
            f"[Memory] {label} - Process RSS: {rss_mb:.1f}MB, "
            f"System Available: {avail_mb:.1f}MB, Usage: {usage_pct:.1f}%"
        )
    except Exception as e:
        logger.error(f"Failed to log memory: {e}")


def cleanup_memory():
    """
    強制的にGCを実行し、PyTorchのGPUキャッシュを解放する。
    """
    import gc

    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except (ImportError, RuntimeError):
        pass


def register_model_activity(service_instance, unload_delay: int = 300):
    """
    モデルのアクティビティを記録し、一定時間後にアンロードするようにタイマーを設定する。
    service_instance は 'unload' メソッド（非同期推奨）を持っている必要がある。
    """
    import time

    service_instance._last_used = time.time()

    # 既存のタイマーがあればキャンセル
    if hasattr(service_instance, "_unload_timer_task") and service_instance._unload_timer_task:
        service_instance._unload_timer_task.cancel()

    async def _wait_and_unload():
        try:
            await asyncio.sleep(unload_delay)
            if hasattr(service_instance, "unload"):
                if asyncio.iscoroutinefunction(service_instance.unload):
                    await service_instance.unload()
                else:
                    service_instance.unload()
        except asyncio.CancelledError:
            pass

    service_instance._unload_timer_task = asyncio.create_task(_wait_and_unload())

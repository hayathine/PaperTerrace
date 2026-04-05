import time
from typing import Dict

from common.logger import ServiceLogger

log = ServiceLogger("CircuitBreaker")


class CircuitBreakerError(Exception):
    """回路ブレーカーエラー"""

    pass


class CircuitBreaker:
    """
    サービス間の通信の失敗を追跡し、失敗が閾値を超えた場合に
    リクエストを遮断（オープン状態）してシステムの過負荷を防ぎます。
    """

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._state: Dict[str, dict] = {}

    def _ensure_service_state(self, service: str):
        if service not in self._state:
            self._state[service] = {
                "failure_count": 0,
                "last_failure_time": None,
                "circuit_open": False,
            }

    def check(self, service: str):
        """回路ブレーカーの状態をチェックし、オープンであれば例外をスローする。"""
        self._ensure_service_state(service)
        state = self._state[service]

        if state["circuit_open"]:
            if (
                state["last_failure_time"]
                and time.time() - state["last_failure_time"] > self.recovery_timeout
            ):
                # 回復タイムアウト経過済みならリセット
                state["circuit_open"] = False
                state["failure_count"] = 0
                log.info("circuit_breaker", "回路ブレーカーをリセットしました", service=service)
            else:
                raise CircuitBreakerError(f"推論サービス({service})の回路ブレーカーが開いています")

    def record_success(self, service: str):
        """成功時の記録"""
        self._ensure_service_state(service)
        state = self._state[service]
        state["failure_count"] = 0
        if state["circuit_open"]:
            state["circuit_open"] = False
            log.info("circuit_breaker", "推論サービスが復旧しました", service=service)

    def record_failure(self, service: str):
        """失敗時の記録"""
        self._ensure_service_state(service)
        state = self._state[service]
        state["failure_count"] += 1
        state["last_failure_time"] = time.time()

        if state["failure_count"] >= self.failure_threshold:
            state["circuit_open"] = True
            log.error(
                "circuit_breaker",
                "推論サービスの回路ブレーカーを開きました",
                service=service,
                failure_count=state["failure_count"],
            )

    def is_available(self, service: str) -> bool:
        """例外を投げずに利用可能かどうかを返す。"""
        try:
            self.check(service)
            return True
        except CircuitBreakerError:
            return False

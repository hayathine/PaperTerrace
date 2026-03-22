"""
DSPy module trace recording utility.
Records input/output pairs to BigQuery for later use as DSPy training examples.
"""

import asyncio
import json
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone

from common.logger import get_logger
from common import settings

logger = get_logger(__name__)

_executor = ThreadPoolExecutor(max_workers=1)

MAX_FIELD_LENGTH = 20_000


@dataclass
class TraceContext:
    """Optional context to attach to a DSPy trace record."""

    user_id: str | None = None
    session_id: str | None = None
    paper_id: str | None = None
    is_copied: bool = False
    comment: str | None = None
    candidate_index: int | None = None


def _truncate_values(d: dict, max_len: int = MAX_FIELD_LENGTH) -> dict:
    """Truncate string values in a dict to prevent oversized rows."""
    out = {}
    for k, v in d.items():
        if isinstance(v, str) and len(v) > max_len:
            out[k] = v[:max_len] + "...[truncated]"
        else:
            out[k] = v
    return out


def _prediction_to_dict(prediction) -> dict:
    """Convert a DSPy Prediction to a plain dict."""
    if hasattr(prediction, "toDict"):
        return prediction.toDict()
    # Fallback: iterate over known keys
    return {
        k: getattr(prediction, k, None)
        for k in dir(prediction)
        if not k.startswith("_")
    }


def _extract_answer(outputs: dict) -> str | None:
    """Extract a representative 'answer' from the prediction outputs."""
    for key in ["answer", "reply", "explanation", "content", "summary"]:
        if key in outputs and outputs[key]:
            return str(outputs[key])
    return None


def _get_last_prompt() -> str | None:
    """Try to get the last prompt from dspy history.

    DSPy 2.5+ stores prompts in `messages` (list of role/content dicts)
    rather than the `prompt` key (which is always None).
    Concatenate system + user messages as the prompt representation.
    """
    try:
        import dspy

        if (
            hasattr(dspy.settings, "lm")
            and dspy.settings.lm
            and hasattr(dspy.settings.lm, "history")
            and dspy.settings.lm.history
        ):
            entry = dspy.settings.lm.history[-1]
            # DSPy 2.5+: prompt is in messages list
            messages = entry.get("messages")
            if messages:
                parts = []
                for msg in messages:
                    role = msg.get("role", "")
                    content = msg.get("content", "")
                    if isinstance(content, str) and content:
                        parts.append(f"[{role}]\n{content}")
                if parts:
                    return "\n\n".join(parts)
            # fallback: legacy prompt field
            return entry.get("prompt")
    except (ImportError, AttributeError, IndexError, KeyError):
        pass
    return None


def _save_trace_sync(
    trace_id: str,
    module_name: str,
    signature: str,
    inputs: dict,
    outputs: dict,
    latency_ms: int | None,
    is_success: bool,
    error_msg: str | None,
    context: TraceContext | None,
    is_copied: bool = False,
    prompt: str | None = None,
    answer: str | None = None,
    candidate_index: int | None = None,
):
    """Synchronously write a trace record to BigQuery. Runs in background thread."""
    try:
        env = settings.get("APP_ENV", "local")
        if env in ("local", "testing"):
            logger.debug("Skipping DSPy trace recording in %s environment.", env)
            return

        from app.providers.bigquery_log import BigQueryLogClient

        bq = BigQueryLogClient.get_instance()
        row = {
            "trace_id": trace_id,
            "module_name": module_name,
            "signature": signature,
            "inputs": json.dumps(_truncate_values(inputs), ensure_ascii=False),
            "outputs": json.dumps(_truncate_values(outputs), ensure_ascii=False),
            "user_id": context.user_id if context else None,
            "session_id": context.session_id if context else None,
            "paper_id": context.paper_id if context else None,
            "model_name": settings.get(
                "DSPY_MODEL", "vertex_ai/gemini-2.5-flash-lite"
            ),
            "latency_ms": latency_ms,
            "is_success": is_success,
            "is_copied": is_copied or (context.is_copied if context else False),
            "error_msg": error_msg,
            "comment": context.comment if context else None,
            "prompt": prompt,
            "answer": answer,
            "candidate_index": candidate_index if candidate_index is not None else (context.candidate_index if context else None),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        bq.streaming_insert("dspy_traces", [row])
    except Exception:
        logger.exception("Failed to save DSPy trace %s", trace_id)


def save_trace(
    module_name: str,
    signature: str,
    inputs: dict,
    outputs: dict,
    latency_ms: int | None = None,
    is_success: bool = True,
    error_msg: str | None = None,
    context: TraceContext | None = None,
    prompt: str | None = None,
    answer: str | None = None,
) -> str:
    """Fire-and-forget trace save via background thread. Returns trace_id."""
    trace_id = str(uuid.uuid4())
    _executor.submit(
        _save_trace_sync,
        trace_id,
        module_name,
        signature,
        inputs,
        outputs,
        latency_ms,
        is_success,
        error_msg,
        context,
        is_copied=context.is_copied if context else False,
        prompt=prompt,
        answer=answer,
        candidate_index=context.candidate_index if context else None,
    )
    return trace_id


_TRANSIENT_ERROR_NAMES = frozenset({
    "ResourceExhausted",
    "ServiceUnavailable",
    "DeadlineExceeded",
    "InternalServerError",
    "TooManyRequests",
    "GatewayTimeout",
})

_MAX_RETRIES = 3
_BASE_DELAY = 1.0  # seconds


def _is_transient(exc: Exception) -> bool:
    """一時的なエラー（リトライ対象）かどうかを判定する。"""
    if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
        return True
    exc_name = type(exc).__name__
    if exc_name in _TRANSIENT_ERROR_NAMES:
        return True
    # litellm / google-api-core がラップしたエラーの status_code を確認
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if isinstance(status, int) and status in (429, 500, 502, 503, 504):
        return True
    return False


async def trace_dspy_call(
    module_name: str,
    signature_name: str,
    module_callable,
    inputs: dict,
    context: TraceContext | None = None,
):
    """
    Call a DSPy module and record the trace (Async version).
    一時的なエラー（レート制限・タイムアウト・接続障害）は最大3回リトライする。

    Args:
        module_name: e.g. "ChatModule"
        signature_name: e.g. "ChatGeneral"
        module_callable: the DSPy module instance (callable)
        inputs: dict of keyword arguments to pass to the module
        context: optional TraceContext with user/session/paper IDs

    Returns:
        Tuple of (DSPy Prediction result, trace_id string)
    """
    last_exception: Exception | None = None

    for attempt in range(_MAX_RETRIES):
        start = time.perf_counter()
        trace_id = "error"
        try:
            # Run sync DSPy module in a separate thread to avoid event loop issues
            result = await asyncio.to_thread(module_callable, **inputs)
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            outputs = _prediction_to_dict(result)
            prompt = _get_last_prompt()
            answer = _extract_answer(outputs)
            trace_id = save_trace(
                module_name=module_name,
                signature=signature_name,
                inputs=inputs,
                outputs=outputs,
                latency_ms=elapsed_ms,
                context=context,
                prompt=prompt,
                answer=answer,
            )
            return result, trace_id
        except Exception as e:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            last_exception = e

            is_last_attempt = attempt == _MAX_RETRIES - 1
            if not is_last_attempt and _is_transient(e):
                delay = _BASE_DELAY * (2 ** attempt)
                logger.warning(
                    "DSPy call %s.%s failed (attempt %d/%d), retrying in %.1fs: %s",
                    module_name, signature_name, attempt + 1, _MAX_RETRIES, delay, e,
                )
                # 失敗トレースも記録（is_success=False）
                save_trace(
                    module_name=module_name,
                    signature=signature_name,
                    inputs=inputs,
                    outputs={},
                    latency_ms=elapsed_ms,
                    is_success=False,
                    error_msg=f"[retry {attempt + 1}/{_MAX_RETRIES}] {e}",
                    context=context,
                )
                await asyncio.sleep(delay)
                continue

            # 恒久的エラー or 最終試行 → トレース記録して raise
            trace_id = save_trace(
                module_name=module_name,
                signature=signature_name,
                inputs=inputs,
                outputs={},
                latency_ms=elapsed_ms,
                is_success=False,
                error_msg=str(e),
                context=context,
            )
            raise

    # Should not reach here, but safety net
    raise last_exception  # type: ignore[misc]

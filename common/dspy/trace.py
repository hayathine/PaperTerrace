"""
DSPy module trace recording utility.
Records input/output pairs for later use as DSPy training examples.
"""

import json
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from common.logger import get_logger

logger = get_logger(__name__)

_executor = ThreadPoolExecutor(max_workers=1)

MAX_FIELD_LENGTH = 20_000


@dataclass
class TraceContext:
    """Optional context to attach to a DSPy trace record."""

    user_id: str | None = None
    session_id: str | None = None
    paper_id: str | None = None


def _truncate_values(d: dict, max_len: int = MAX_FIELD_LENGTH) -> dict:
    """Truncate string values in a dict to prevent oversized DB rows."""
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
    return {k: getattr(prediction, k, None) for k in dir(prediction) if not k.startswith("_")}


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
):
    """Synchronously write a trace record to the DB. Runs in background thread."""
    try:
        # Lazy import to avoid circular imports and keep common/ lightweight
        from app.database import get_db_context
        from app.models.orm.dspy_trace import DspyTrace

        with get_db_context() as db:
            trace = DspyTrace(
                trace_id=trace_id,
                module_name=module_name,
                signature=signature,
                inputs=json.dumps(_truncate_values(inputs), ensure_ascii=False),
                outputs=json.dumps(_truncate_values(outputs), ensure_ascii=False),
                user_id=context.user_id if context else None,
                session_id=context.session_id if context else None,
                paper_id=context.paper_id if context else None,
                model_name=os.environ.get("DSPY_GEMINI_MODEL", "gemini/gemini-2.5-flash-lite"),
                latency_ms=latency_ms,
                is_success=is_success,
                error_msg=error_msg,
            )
            db.add(trace)
            db.commit()
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
):
    """Fire-and-forget trace save via background thread."""
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
    )


def trace_dspy_call(
    module_name: str,
    signature_name: str,
    module_callable,
    inputs: dict,
    context: TraceContext | None = None,
):
    """
    Call a DSPy module and record the trace.

    Args:
        module_name: e.g. "ChatModule"
        signature_name: e.g. "ChatGeneral"
        module_callable: the DSPy module instance (callable)
        inputs: dict of keyword arguments to pass to the module
        context: optional TraceContext with user/session/paper IDs

    Returns:
        The DSPy Prediction result (same as calling module_callable(**inputs))
    """
    start = time.perf_counter()
    try:
        result = module_callable(**inputs)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        outputs = _prediction_to_dict(result)
        save_trace(
            module_name=module_name,
            signature=signature_name,
            inputs=inputs,
            outputs=outputs,
            latency_ms=elapsed_ms,
            context=context,
        )
        return result
    except Exception as e:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        save_trace(
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

"""Google GenAI SDK 共通ヘルパー。

例外クラス・TypedDict・パース/Part 生成ユーティリティを提供する。
ai_provider.py から import して使用する。
"""

from typing import Any, TypedDict

from pydantic import BaseModel

from common.logger import ServiceLogger

log = ServiceLogger("AIProvider")


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class AIProviderError(Exception):
    """Base exception for AI Provider errors."""


class AIGenerationError(AIProviderError):
    """Exception for generation failures."""


# ---------------------------------------------------------------------------
# TypedDict
# ---------------------------------------------------------------------------


class GenConfig(TypedDict, total=False):
    """Configuration for AI generation."""

    temperature: float
    max_output_tokens: int
    top_k: int
    top_p: float
    response_mime_type: str
    response_json_schema: Any
    response_schema: Any
    system_instruction: str
    cached_content: str
    tools: list[Any]


# ---------------------------------------------------------------------------
# Response parsers
# ---------------------------------------------------------------------------


def _parse_structured_response(
    response: Any,
    response_model: type[BaseModel],
    operation: str,
    raise_on_error: bool = True,
    fallback_json: str = "{}",
) -> Any:
    """AIレスポンスから Pydantic モデルをパースする共通ヘルパー。

    1. response.parsed を優先（google-genai SDK 1.0+ の構造化出力）
    2. response.text のマークダウンフェンス除去後に model_validate_json でフォールバック
    """
    try:
        if hasattr(response, "parsed") and response.parsed is not None:
            if isinstance(response.parsed, response_model):
                return response.parsed
            if isinstance(response.parsed, dict):
                return response_model.model_validate(response.parsed)

        text_to_parse = (response.text or "").strip()
        if text_to_parse.startswith("```json"):
            text_to_parse = text_to_parse[7:].strip("` \n")
        elif text_to_parse.startswith("```"):
            text_to_parse = text_to_parse[3:].strip("` \n")
        return response_model.model_validate_json(text_to_parse)
    except Exception as parse_err:
        log.error(operation, "構造化出力のパースに失敗しました", error=str(parse_err))
        if raise_on_error:
            raise AIGenerationError(
                f"Failed to parse structured output: {parse_err}"
            ) from parse_err
        return response_model.model_validate_json(response.text or fallback_json)


def _extract_grounding_metadata(response: Any) -> dict | None:
    """レスポンスから Grounding metadata を辞書形式に変換する。"""
    try:
        if not (response.candidates and response.candidates[0].grounding_metadata):
            return None
        gm = response.candidates[0].grounding_metadata
        log.debug(
            "grounding_metadata",
            "Groundingメタデータが見つかりました",
            metadata_type=str(type(gm)),
            has_chunks=bool(hasattr(gm, "grounding_chunks") and gm.grounding_chunks),
            has_supports=bool(hasattr(gm, "grounding_supports") and gm.grounding_supports),
        )
        grounding_data: dict = {}
        if hasattr(gm, "grounding_chunks") and gm.grounding_chunks:
            grounding_data["chunks"] = []
            for chunk in gm.grounding_chunks:
                chunk_dict = {}
                if hasattr(chunk, "web") and chunk.web:
                    chunk_dict["web"] = {"uri": chunk.web.uri, "title": chunk.web.title}
                if hasattr(chunk, "retrieved_context") and chunk.retrieved_context:
                    chunk_dict["retrieved_context"] = {
                        "uri": chunk.retrieved_context.uri,
                        "title": chunk.retrieved_context.title,
                        "text": chunk.retrieved_context.text,
                    }
                grounding_data["chunks"].append(chunk_dict)
        if hasattr(gm, "grounding_supports") and gm.grounding_supports:
            grounding_data["supports"] = []
            for support in gm.grounding_supports:
                grounding_data["supports"].append(
                    {
                        "segment_text": (
                            support.segment.text if hasattr(support, "segment") else ""
                        ),
                        "indices": (
                            list(support.grounding_chunk_indices)
                            if hasattr(support, "grounding_chunk_indices")
                            else []
                        ),
                        "confidence_scores": (
                            list(support.confidence_scores)
                            if hasattr(support, "confidence_scores")
                            else []
                        ),
                    }
                )
        return grounding_data or None
    except Exception as e:
        log.warning("grounding_metadata", "Groundingメタデータの抽出に失敗しました", error=str(e))
        return None


# ---------------------------------------------------------------------------
# Part builders
# ---------------------------------------------------------------------------


def _build_image_part(
    types: Any, image_bytes: bytes | None, image_uri: str | None, mime_type: str
) -> Any:
    """image_bytes か image_uri から Part オブジェクトを生成する。"""
    if image_uri:
        return types.Part.from_uri(file_uri=image_uri, mime_type=mime_type)
    if image_bytes:
        return types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
    return None


def _build_pdf_part(types: Any, pdf_bytes: bytes | str) -> Any:
    """pdf_bytes (bytes or gs:// URI) から Part オブジェクトを生成する。"""
    if isinstance(pdf_bytes, str) and pdf_bytes.startswith("gs://"):
        return types.Part.from_uri(file_uri=pdf_bytes, mime_type="application/pdf")
    return types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")


def _build_cache_parts(types: Any, contents: Any) -> list:
    """create_context_cache 用に contents を Part リストに変換する。"""
    if isinstance(contents, str):
        if contents.startswith("gs://"):
            return [types.Part.from_uri(file_uri=contents, mime_type="application/pdf")]
        return [types.Part.from_text(text=contents)]
    if isinstance(contents, bytes):
        return [types.Part.from_bytes(data=contents, mime_type="application/pdf")]
    return contents

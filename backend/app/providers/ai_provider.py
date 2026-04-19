"""AI プロバイダー抽象層。

AIProviderInterface (ABC) と、Google GenAI SDK 共通実装 GenAIProviderBase、
具象クラス GeminiProvider / VertexAIProvider を提供する。
"""

import os
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

from common.config import settings  # noqa: F401  secrets/.env の一括ロードを保証
from common.logger import ServiceLogger

from .genai_helpers import (
    AIGenerationError,
    AIProviderError,
    GenConfig,
    _build_cache_parts,
    _build_image_part,
    _build_pdf_part,
    _extract_grounding_metadata,
    _parse_structured_response,
)

log = ServiceLogger("AIProvider")

__all__ = [
    "AIProviderError",
    "AIGenerationError",
    "GenConfig",
    "AIProviderInterface",
    "GenAIProviderBase",
    "GeminiProvider",
    "VertexAIProvider",
    "get_ai_provider",
]


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------


class AIProviderInterface(ABC):
    """Abstract interface for AI providers."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        context: str = "",
        model: str | None = None,
        enable_search: bool = False,
        response_model: type[BaseModel] | None = None,
        system_instruction: str | None = None,
        cached_content_name: str | None = None,
    ) -> Any:
        """Generate text or structured response from prompt."""
        ...

    @abstractmethod
    async def generate_with_image(
        self,
        prompt: str,
        image_bytes: bytes | None = None,
        mime_type: str = "image/jpeg",
        model: str | None = None,
        response_model: type[BaseModel] | None = None,
        system_instruction: str | None = None,
        cached_content_name: str | None = None,
        image_uri: str | None = None,
        max_tokens: int | None = None,
    ) -> Any:
        """Generate text or structured response from prompt with image input.

        image_bytes か image_uri のいずれかを指定する。
        image_uri (gs://bucket/blob) を指定した場合、GCS から直接取得するため
        バックエンドでのダウンロードが不要になる。
        """
        ...

    @abstractmethod
    async def generate_with_pdf(
        self,
        prompt: str,
        pdf_bytes: bytes | None = None,
        model: str | None = None,
        cached_content_name: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Generate text response from prompt with PDF input."""
        ...

    @abstractmethod
    async def generate_with_images(
        self,
        prompt: str,
        images_list: list[bytes],
        mime_type: str = "image/jpeg",
        model: str | None = None,
        response_model: type[BaseModel] | None = None,
        system_instruction: str | None = None,
        cached_content_name: str | None = None,
        max_tokens: int | None = None,
    ) -> Any:
        """Generate text response from prompt with multiple images."""
        pass

    @abstractmethod
    async def generate_stream(
        self,
        prompt: str,
        context: str = "",
        model: str | None = None,
        system_instruction: str | None = None,
        cached_content_name: str | None = None,
    ):
        """Yield text chunks from prompt."""
        ...

    @abstractmethod
    async def generate_with_image_stream(
        self,
        prompt: str,
        image_bytes: bytes | None = None,
        mime_type: str = "image/jpeg",
        model: str | None = None,
        system_instruction: str | None = None,
        cached_content_name: str | None = None,
        image_uri: str | None = None,
    ):
        """Yield text chunks from prompt with image."""
        ...

    @abstractmethod
    async def generate_with_pdf_stream(
        self,
        prompt: str,
        pdf_bytes: bytes | None = None,
        model: str | None = None,
        cached_content_name: str | None = None,
        max_tokens: int | None = None,
    ):
        """Yield text chunks from prompt with PDF."""
        ...

    @abstractmethod
    async def count_tokens(self, contents: Any, model: str | None = None) -> int:
        """Count tokens for the given contents."""
        ...

    @abstractmethod
    async def create_context_cache(
        self,
        model: str,
        contents: Any,
        system_instruction: str | None = None,
        ttl_minutes: int = 60,
    ) -> str:
        """Create a context cache and return its name."""
        ...

    @abstractmethod
    async def delete_context_cache(self, cache_name: str) -> None:
        """Delete a context cache by name."""
        ...

    def _check_truncation(
        self, response: Any, model: str, method: str, max_tokens: int
    ) -> None:
        """レスポンスが最大トークン数で途切れた場合に警告ログを出力する。"""
        try:
            if response.candidates and response.candidates[0].finish_reason:
                reason = str(response.candidates[0].finish_reason)
                if "MAX_TOKENS" in reason:
                    log.warning(
                        f"{method}_truncated",
                        "AIのレスポンスが途切れました（最大出力トークン数に達しました）",
                        model=model,
                        max_tokens=max_tokens,
                        finish_reason=reason,
                    )
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Shared base for Google GenAI SDK providers
# ---------------------------------------------------------------------------


class GenAIProviderBase(AIProviderInterface):
    """Google GenAI SDK を使うプロバイダー共通実装。

    サブクラスは __init__ で self._types / self.client / self.model /
    self.temperature / self.max_tokens を初期化すること。
    必要に応じて _get_client / _multimodal_schema_config /
    _post_process_text_response をオーバーライドする。
    """

    # サブクラスで設定するクラス属性
    _provider_name: str = "genai"
    _parse_raise_on_error: bool = True  # 単体生成の構造化パースエラーを例外にするか

    # __init__ で初期化される インスタンス属性（型ヒントのみ）
    _types: Any
    client: Any
    model: str
    temperature: float
    max_tokens: int

    # ------------------------------------------------------------------
    # Extension points
    # ------------------------------------------------------------------

    def _get_client(self, model: str) -> Any:
        """使用する genai.Client を返す（Vertex はモデル別に切り替え）。"""
        return self.client

    def _multimodal_schema_config(self, response_model: type[BaseModel]) -> dict:
        """マルチモーダルメソッドの構造化出力設定を返す。"""
        return {
            "response_mime_type": "application/json",
            "response_json_schema": response_model.model_json_schema(),
        }

    def _post_process_text_response(
        self, response: Any, enable_search: bool, text: str
    ) -> Any:
        """テキスト生成レスポンスの後処理（Gemini はグラウンディング抽出でオーバーライド）。"""
        return text

    # ------------------------------------------------------------------
    # generate
    # ------------------------------------------------------------------

    async def generate(
        self,
        prompt: str,
        context: str = "",
        model: str | None = None,
        enable_search: bool = False,
        response_model: type[BaseModel] | None = None,
        system_instruction: str | None = None,
        cached_content_name: str | None = None,
    ) -> Any:
        """Generate text or structured response from prompt."""
        target_model = model or self.model
        pname = self._provider_name
        try:
            full_prompt = f"{context}\n\n{prompt}" if context else prompt
            log.debug(
                f"{pname}_generate",
                "生成リクエスト",
                prompt_length=len(full_prompt),
                model=target_model,
                search=enable_search,
                structured=response_model is not None,
            )

            tools = None
            if enable_search:
                tools = [self._types.Tool(google_search=self._types.GoogleSearch())]

            config_params: GenConfig = {
                "temperature": self.temperature,
                "max_output_tokens": self.max_tokens,
            }
            if tools and not cached_content_name:
                config_params["tools"] = tools
            if response_model:
                config_params["response_mime_type"] = "application/json"
                config_params["response_json_schema"] = response_model.model_json_schema()
            if system_instruction and not cached_content_name:
                config_params["system_instruction"] = system_instruction
            if cached_content_name:
                config_params["cached_content"] = cached_content_name

            config = self._types.GenerateContentConfig(**config_params)
            contents = prompt if cached_content_name else full_prompt

            response = await self._get_client(target_model).aio.models.generate_content(
                model=target_model,
                contents=contents,
                config=config,
            )
            self._check_truncation(response, target_model, f"{pname}_generate", self.max_tokens)

            if response_model:
                return _parse_structured_response(
                    response,
                    response_model,
                    f"{pname}_generate",
                    raise_on_error=self._parse_raise_on_error,
                )

            result_text = str(response.text or "").strip()
            return self._post_process_text_response(response, enable_search, result_text)

        except Exception as e:
            log.exception(f"{pname}_generate", "生成に失敗しました", model=target_model)
            raise AIGenerationError(f"Generation failed: {e}") from e

    # ------------------------------------------------------------------
    # generate_with_image
    # ------------------------------------------------------------------

    async def generate_with_image(
        self,
        prompt: str,
        image_bytes: bytes | None = None,
        mime_type: str = "image/jpeg",
        model: str | None = None,
        response_model: type[BaseModel] | None = None,
        system_instruction: str | None = None,
        cached_content_name: str | None = None,
        image_uri: str | None = None,
        max_tokens: int | None = None,
    ) -> Any:
        """Generate text or structured response from prompt with image input."""
        if image_bytes is None and image_uri is None:
            raise ValueError("image_bytes か image_uri のいずれかを指定してください")

        target_model = model or self.model
        pname = self._provider_name
        try:
            log.debug(
                f"{pname}_image",
                "画像リクエスト",
                image_size=len(image_bytes) if image_bytes else 0,
                image_uri=image_uri,
                mime_type=mime_type,
                model=target_model,
                structured=response_model is not None,
            )

            config_params: GenConfig = {
                "temperature": self.temperature,
                "max_output_tokens": max_tokens or self.max_tokens,
            }
            if response_model:
                config_params.update(self._multimodal_schema_config(response_model))
            if system_instruction:
                config_params["system_instruction"] = system_instruction
            if cached_content_name:
                config_params["cached_content"] = cached_content_name

            config = self._types.GenerateContentConfig(**config_params)
            image_part = _build_image_part(self._types, image_bytes, image_uri, mime_type)
            contents = [image_part, prompt] if image_part else [prompt]

            response = await self._get_client(target_model).aio.models.generate_content(
                model=target_model,
                contents=contents,
                config=config,
            )
            self._check_truncation(response, target_model, f"{pname}_image", self.max_tokens)

            if response_model:
                return _parse_structured_response(
                    response,
                    response_model,
                    f"{pname}_image",
                    raise_on_error=self._parse_raise_on_error,
                )

            result = (response.text or "").strip()
            log.debug(f"{pname}_image", "画像レスポンス", response_length=len(result))
            return result

        except Exception as e:
            log.exception(f"{pname}_image", "画像生成に失敗しました", mime_type=mime_type)
            raise AIGenerationError(f"Image analysis failed: {e}") from e

    # ------------------------------------------------------------------
    # generate_with_images
    # ------------------------------------------------------------------

    async def generate_with_images(
        self,
        prompt: str,
        images_list: list[bytes],
        mime_type: str = "image/jpeg",
        model: str | None = None,
        response_model: type[BaseModel] | None = None,
        system_instruction: str | None = None,
        cached_content_name: str | None = None,
        max_tokens: int | None = None,
    ) -> Any:
        """Generate text response from prompt with multiple images."""
        target_model = model or self.model
        effective_max_tokens = max_tokens or self.max_tokens
        pname = self._provider_name
        try:
            log.debug(
                f"{pname}_multi_image",
                "複数画像リクエスト",
                image_count=len(images_list),
                model=target_model,
                structured=response_model is not None,
            )

            config_params: GenConfig = {
                "temperature": self.temperature,
                "max_output_tokens": effective_max_tokens,
            }
            if response_model:
                config_params.update(self._multimodal_schema_config(response_model))
            if system_instruction:
                config_params["system_instruction"] = system_instruction
            if cached_content_name:
                config_params["cached_content"] = cached_content_name

            config = self._types.GenerateContentConfig(**config_params)

            if cached_content_name:
                contents = [prompt]
            else:
                contents = [
                    self._types.Part.from_bytes(data=img, mime_type=mime_type)
                    for img in images_list
                ]
                contents.append(prompt)

            response = await self._get_client(target_model).aio.models.generate_content(
                model=target_model,
                contents=contents,
                config=config,
            )
            self._check_truncation(
                response, target_model, f"{pname}_multi_image", effective_max_tokens
            )

            if response_model:
                return _parse_structured_response(
                    response, response_model, f"{pname}_multi_image", raise_on_error=False
                )

            return (response.text or "").strip()

        except Exception as e:
            log.exception(f"{pname}_multi_image", "複数画像生成に失敗しました")
            raise AIGenerationError(f"Multi-image analysis failed: {e}") from e

    # ------------------------------------------------------------------
    # generate_with_pdf
    # ------------------------------------------------------------------

    async def generate_with_pdf(
        self,
        prompt: str,
        pdf_bytes: bytes | None = None,
        model: str | None = None,
        cached_content_name: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Generate text response from prompt with PDF input."""
        target_model = model or self.model
        pname = self._provider_name
        try:
            log.debug(
                f"{pname}_pdf",
                "PDFリクエスト",
                pdf_size=len(pdf_bytes) if pdf_bytes else 0,
                model=target_model,
                cached=cached_content_name is not None,
            )

            config_params: GenConfig = {
                "temperature": self.temperature,
                "max_output_tokens": max_tokens or self.max_tokens,
            }
            if cached_content_name:
                config_params["cached_content"] = cached_content_name
            config = self._types.GenerateContentConfig(**config_params)

            if not cached_content_name and pdf_bytes:
                contents = [_build_pdf_part(self._types, pdf_bytes), prompt]
            else:
                contents = [prompt]

            response = await self._get_client(target_model).aio.models.generate_content(
                model=target_model,
                contents=contents,
                config=config,
            )
            self._check_truncation(
                response, target_model, f"{pname}_pdf", max_tokens or self.max_tokens
            )
            result = str(response.text or "").strip()
            log.debug(f"{pname}_pdf", "PDFレスポンス", response_length=len(result))
            return result

        except Exception as e:
            log.exception(
                f"{pname}_pdf",
                "PDF生成に失敗しました",
                pdf_size=len(pdf_bytes) if pdf_bytes else 0,
            )
            raise AIGenerationError(f"PDF analysis failed: {e}") from e

    # ------------------------------------------------------------------
    # Streaming methods
    # ------------------------------------------------------------------

    async def generate_stream(
        self,
        prompt: str,
        context: str = "",
        model: str | None = None,
        system_instruction: str | None = None,
        cached_content_name: str | None = None,
    ):
        """Yield text chunks from prompt."""
        target_model = model or self.model
        pname = self._provider_name
        try:
            full_prompt = f"{context}\n\n{prompt}" if context else prompt
            config_params: dict = {
                "temperature": self.temperature,
                "max_output_tokens": self.max_tokens,
            }
            if system_instruction and not cached_content_name:
                config_params["system_instruction"] = system_instruction
            if cached_content_name:
                config_params["cached_content"] = cached_content_name

            config = self._types.GenerateContentConfig(**config_params)
            contents = prompt if cached_content_name else full_prompt

            response_stream = (
                await self._get_client(target_model).aio.models.generate_content_stream(
                    model=target_model,
                    contents=contents,
                    config=config,
                )
            )
            async for chunk in response_stream:
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            log.exception(f"{pname}_stream", "ストリーミング生成に失敗しました")
            raise AIGenerationError(f"Streaming failed: {e}")

    async def generate_with_image_stream(
        self,
        prompt: str,
        image_bytes: bytes | None = None,
        mime_type: str = "image/jpeg",
        model: str | None = None,
        system_instruction: str | None = None,
        cached_content_name: str | None = None,
        image_uri: str | None = None,
    ):
        """Yield text chunks from prompt with image."""
        target_model = model or self.model
        pname = self._provider_name
        try:
            config_params: dict = {
                "temperature": self.temperature,
                "max_output_tokens": self.max_tokens,
            }
            if system_instruction:
                config_params["system_instruction"] = system_instruction
            if cached_content_name:
                config_params["cached_content"] = cached_content_name

            config = self._types.GenerateContentConfig(**config_params)
            image_part = _build_image_part(self._types, image_bytes, image_uri, mime_type)
            contents = [image_part, prompt] if image_part else [prompt]

            response_stream = (
                await self._get_client(target_model).aio.models.generate_content_stream(
                    model=target_model,
                    contents=contents,
                    config=config,
                )
            )
            async for chunk in response_stream:
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            log.exception(f"{pname}_image_stream", "画像ストリーミングに失敗しました")
            raise AIGenerationError(f"Image streaming failed: {e}")

    async def generate_with_pdf_stream(
        self,
        prompt: str,
        pdf_bytes: bytes | None = None,
        model: str | None = None,
        cached_content_name: str | None = None,
        max_tokens: int | None = None,
    ):
        """Yield text chunks from prompt with PDF."""
        target_model = model or self.model
        pname = self._provider_name
        try:
            config_params: dict = {
                "temperature": self.temperature,
                "max_output_tokens": max_tokens or self.max_tokens,
            }
            if cached_content_name:
                config_params["cached_content"] = cached_content_name
            config = self._types.GenerateContentConfig(**config_params)

            contents = (
                [prompt]
                if cached_content_name
                else [_build_pdf_part(self._types, pdf_bytes), prompt]
            )

            response_stream = (
                await self._get_client(target_model).aio.models.generate_content_stream(
                    model=target_model,
                    contents=contents,
                    config=config,
                )
            )
            async for chunk in response_stream:
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            log.exception(f"{pname}_pdf_stream", "PDF ストリーミングに失敗しました")
            raise AIGenerationError(f"PDF streaming failed: {e}")

    # ------------------------------------------------------------------
    # Token counting & cache management
    # ------------------------------------------------------------------

    async def count_tokens(self, contents: Any, model: str | None = None) -> int:
        """Count tokens using the provider's API."""
        target_model = model or self.model
        pname = self._provider_name
        try:
            resp = await self._get_client(target_model).aio.models.count_tokens(
                model=target_model, contents=contents
            )
            return int(resp.total_tokens or 0)
        except Exception as e:
            log.error(f"count_tokens_{pname}", "トークン数のカウントに失敗しました", error=str(e))
            return 0

    async def create_context_cache(
        self,
        model: str,
        contents: Any,
        system_instruction: str | None = None,
        ttl_minutes: int = 60,
    ) -> str:
        """Create a context cache and return its name."""
        pname = self._provider_name
        try:
            log.info(
                f"create_context_cache_{pname}",
                "コンテキストキャッシュを作成中",
                model=model,
                ttl_minutes=ttl_minutes,
            )
            parts = _build_cache_parts(self._types, contents)
            cache = await self._get_client(model).aio.caches.create(
                model=model,
                config=self._types.CreateCachedContentConfig(
                    contents=parts,
                    system_instruction=system_instruction,
                    ttl=f"{ttl_minutes * 60}s",
                ),
            )
            log.info(
                f"create_context_cache_{pname}",
                "コンテキストキャッシュを作成しました",
                cache_name=cache.name,
            )
            return cache.name or ""
        except Exception as e:
            log.error(
                f"create_context_cache_{pname}",
                "キャッシュの作成に失敗しました",
                error=str(e),
            )
            raise AIProviderError(f"Cache creation failed: {e}")

    async def delete_context_cache(self, cache_name: str) -> None:
        """Delete a context cache by name."""
        pname = self._provider_name
        try:
            await self.client.aio.caches.delete(name=cache_name)
            log.info(
                f"delete_context_cache_{pname}",
                "コンテキストキャッシュを削除しました",
                cache_name=cache_name,
            )
        except Exception as e:
            log.error(
                f"delete_context_cache_{pname}",
                "キャッシュの削除に失敗しました",
                cache_name=cache_name,
                error=str(e),
            )


# ---------------------------------------------------------------------------
# Concrete providers
# ---------------------------------------------------------------------------


class GeminiProvider(GenAIProviderBase):
    """Gemini API (google.genai) provider implementation."""

    _provider_name = "gemini"
    _parse_raise_on_error = True

    def __init__(self):
        from google import genai
        from google.genai import types

        self._types = types

        api_key = settings.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        self.client = genai.Client(api_key=api_key, vertexai=False)
        self.model = settings.get("MODEL_OCR", "gemini-2.5-flash")
        self.temperature = float(settings.get("AI_TEMPERATURE", "0.1"))
        self.max_tokens = int(settings.get("AI_MAX_OUTPUT_TOKENS", "1024"))
        log.info(
            "gemini_init",
            "GeminiProviderを初期化しました",
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

    def _post_process_text_response(
        self, response: Any, enable_search: bool, text: str
    ) -> Any:
        """グラウンディングメタデータを抽出して返す。"""
        grounding_data = _extract_grounding_metadata(response) if enable_search else None
        log.debug(
            "gemini_generate",
            "Gemini 生成レスポンス",
            response_length=len(text),
            has_grounding=grounding_data is not None,
        )
        if grounding_data:
            return {"text": text, "grounding": grounding_data}
        return text


class VertexAIProvider(GenAIProviderBase):
    """Vertex AI provider implementation using Google GenAI SDK.

    設定:
    - AI_PROVIDER=vertex
    - GCP_PROJECT_ID=your-project-id
    - GCP_LOCATION=us-central1
    - GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json (省略可)
    """

    _provider_name = "vertex"
    _parse_raise_on_error = False

    def __init__(self):
        from google import genai
        from google.genai import types

        self._types = types

        self.project_id = settings.get("GCP_PROJECT_ID")
        self.location = settings.get("GCP_LOCATION", "us-central1")
        self.model = settings.get("VERTEX_MODEL", "gemini-2.5-flash-lite")

        global_models_str = settings.get("GCP_GLOBAL_MODELS", "")
        self.global_models: set[str] = {
            m.strip() for m in global_models_str.split(",") if m.strip()
        }

        if not self.project_id:
            log.warning(
                "vertex_init",
                "GCP_PROJECT_ID が設定されていません。デフォルトの認証情報/設定を使用します。",
            )

        credentials_path = settings.get("GOOGLE_APPLICATION_CREDENTIALS")
        if credentials_path and os.path.exists(credentials_path):
            log.info(
                "vertex_init",
                "サービスアカウントの認証情報を使用します",
                path=credentials_path,
            )
            from google.auth import load_credentials_from_file

            credentials, project = load_credentials_from_file(
                credentials_path,
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
            if not self.project_id and project:
                self.project_id = project
                log.info(
                    "vertex_init", "認証情報からプロジェクトIDを取得しました", project=project
                )
            self.client = genai.Client(
                vertexai=True,
                project=self.project_id,
                location=self.location,
                credentials=credentials,
            )
            self._global_client = (
                genai.Client(
                    vertexai=True,
                    project=self.project_id,
                    location="global",
                    credentials=credentials,
                )
                if self.global_models and self.location != "global"
                else self.client
            )
        else:
            log.info("vertex_init", "アプリケーション デフォルト資格情報 (ADC) を使用します")
            self.client = genai.Client(
                vertexai=True,
                project=self.project_id,
                location=self.location,
            )
            self._global_client = (
                genai.Client(
                    vertexai=True,
                    project=self.project_id,
                    location="global",
                )
                if self.global_models and self.location != "global"
                else self.client
            )

        self.temperature = float(settings.get("AI_TEMPERATURE", "0.1"))
        self.max_tokens = int(settings.get("AI_MAX_OUTPUT_TOKENS", "1024"))
        log.info(
            "vertex_init",
            "VertexAIProviderを初期化しました",
            project=self.project_id,
            location=self.location,
            model=self.model,
            global_models=list(self.global_models),
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

    def _get_client(self, model: str) -> Any:
        """globalロケーション専用モデルは _global_client を返す。"""
        if model in self.global_models:
            return self._global_client
        return self.client

    def _multimodal_schema_config(self, response_model: type[BaseModel]) -> dict:
        # Vertex AI マルチモーダルでは response_json_schema (dict) は
        # 400 INVALID_ARGUMENT になるため response_schema (Pydantic model) を使用
        return {"response_mime_type": "application/json", "response_schema": response_model}


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_ai_provider_instance: AIProviderInterface | None = None


def get_ai_provider() -> AIProviderInterface:
    """設定に応じた AI プロバイダーをシングルトンで返す。

    AI_PROVIDER 設定:
    - "vertex" (デフォルト): Vertex AI を使用
    - "gemini": Gemini API を直接使用
    """
    global _ai_provider_instance

    if _ai_provider_instance is not None:
        return _ai_provider_instance

    provider_type = str(settings.get("AI_PROVIDER", "vertex")).lower()

    if provider_type == "vertex":
        _ai_provider_instance = VertexAIProvider()
    else:
        _ai_provider_instance = GeminiProvider()

    return _ai_provider_instance

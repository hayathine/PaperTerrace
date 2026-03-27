import os
from abc import ABC, abstractmethod
from typing import Any, TypedDict

from pydantic import BaseModel

from common.config import settings  # noqa: F401  secrets/.env の一括ロードを保証
from common.logger import ServiceLogger

log = ServiceLogger("AIProvider")


class AIProviderError(Exception):
    """Base exception for AI Provider errors."""

    pass


class AIGenerationError(AIProviderError):
    """Exception for generation failures."""

    pass


class GenConfig(TypedDict, total=False):
    """Configuration for AI generation."""

    temperature: float
    max_output_tokens: int
    top_k: int
    top_p: float
    response_mime_type: str
    response_json_schema: Any
    system_instruction: str
    cached_content: str
    tools: list[Any]


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
        """Check and log if the response was truncated due to token limits."""
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


class GeminiProvider(AIProviderInterface):
    """Gemini API provider implementation."""

    def __init__(self):
        # コールドスタート最適化: 初回使用時のみインポート
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
        """Generate text response from prompt, optionally as structured data."""
        target_model = model or self.model
        try:
            full_prompt = f"{context}\n\n{prompt}" if context else prompt
            log.debug(
                "gemini_generate",
                "Gemini 生成リクエスト",
                prompt_length=len(full_prompt),
                model=target_model,
                search=enable_search,
                structured=response_model is not None,
            )

            # Configure tools
            tools = None
            if enable_search:
                tools = [self._types.Tool(google_search=self._types.GoogleSearch())]

            # Configure generation config
            config_params: GenConfig = {
                "temperature": self.temperature,
                "max_output_tokens": self.max_tokens,
            }
            if tools and not cached_content_name:
                config_params["tools"] = tools
            if response_model:
                config_params["response_mime_type"] = "application/json"
                config_params["response_json_schema"] = (
                    response_model.model_json_schema()
                )

            if system_instruction and not cached_content_name:
                config_params["system_instruction"] = system_instruction
            if cached_content_name:
                config_params["cached_content"] = cached_content_name

            config = self._types.GenerateContentConfig(**config_params)

            # If using cached content, contents should only be the new prompt
            contents = prompt if cached_content_name else full_prompt

            response = await self.client.aio.models.generate_content(
                model=target_model,
                contents=contents,
                config=config,
            )
            self._check_truncation(
                response, target_model, "gemini_generate", self.max_tokens
            )

            # Log grounding metadata for debugging (Visual Grounding / Evidence)
            try:
                if response.candidates and response.candidates[0].grounding_metadata:
                    gm = response.candidates[0].grounding_metadata
                    log.debug(
                        "gemini_generate",
                        "Groundingメタデータが見つかりました",
                        metadata_type=str(type(gm)),
                        has_chunks=bool(
                            hasattr(gm, "grounding_chunks") and gm.grounding_chunks
                        ),
                        has_supports=bool(
                            hasattr(gm, "grounding_supports") and gm.grounding_supports
                        ),
                    )
            except Exception as e:
                log.warning(
                    "gemini_generate", "Groundingメタデータのログ記録に失敗しました", error=str(e)
                )

            if response_model:
                try:
                    # google-genai SDK 1.0.0+ supports .parsed for structured output
                    if (
                        hasattr(response, "parsed")
                        and response.parsed is not None
                    ):
                        if isinstance(response.parsed, response_model):
                            return response.parsed
                        # If it's a dict (common when using response_json_schema), validate it
                        if isinstance(response.parsed, dict):
                            return response_model.model_validate(response.parsed)

                    # fallback to response.text if parsed is None or not available
                    text_to_parse = (response.text or "").strip()
                    if text_to_parse.startswith("```json"):
                        text_to_parse = text_to_parse[7:].strip("` \n")
                    elif text_to_parse.startswith("```"):
                        text_to_parse = text_to_parse[3:].strip("` \n")
                    return response_model.model_validate_json(text_to_parse)
                except Exception as parse_err:
                    log.error(
                        "gemini_generate",
                        "構造化出力のパースに失敗しました",
                        error=str(parse_err),
                    )
                    raise AIGenerationError(
                        f"Failed to parse structured output: {parse_err}"
                    ) from parse_err

            result_text = str(response.text or "").strip()

            # Extract grounding metadata（Web検索が有効な場合のみ処理）
            grounding_data = None
            if enable_search:
                try:
                    if (
                        response.candidates
                        and response.candidates[0].grounding_metadata
                    ):
                        gm = response.candidates[0].grounding_metadata
                        grounding_data = {}

                        # Convert to serializable format
                        if hasattr(gm, "grounding_chunks") and gm.grounding_chunks:
                            grounding_data["chunks"] = []
                            for chunk in gm.grounding_chunks:
                                chunk_dict = {}
                                if hasattr(chunk, "web") and chunk.web:
                                    chunk_dict["web"] = {
                                        "uri": chunk.web.uri,
                                        "title": chunk.web.title,
                                    }
                                if (
                                    hasattr(chunk, "retrieved_context")
                                    and chunk.retrieved_context
                                ):
                                    chunk_dict["retrieved_context"] = {
                                        "uri": chunk.retrieved_context.uri,
                                        "title": chunk.retrieved_context.title,
                                        "text": chunk.retrieved_context.text,
                                    }
                                grounding_data["chunks"].append(chunk_dict)

                        if hasattr(gm, "grounding_supports") and gm.grounding_supports:
                            grounding_data["supports"] = []
                            for support in gm.grounding_supports:
                                support_dict = {
                                    "segment_text": support.segment.text
                                    if hasattr(support, "segment")
                                    else "",
                                    "indices": list(support.grounding_chunk_indices)
                                    if hasattr(support, "grounding_chunk_indices")
                                    else [],
                                    "confidence_scores": list(support.confidence_scores)
                                    if hasattr(support, "confidence_scores")
                                    else [],
                                }
                                grounding_data["supports"].append(support_dict)
                except Exception as e:
                    log.warning(
                        "gemini_generate",
                        "Groundingメタデータの抽出に失敗しました",
                        error=str(e),
                    )

            log.debug(
                "gemini_generate",
                "Gemini 生成レスポンス",
                response_length=len(result_text),
                has_grounding=grounding_data is not None,
            )

            if grounding_data:
                return {"text": result_text, "grounding": grounding_data}
            return result_text
        except Exception as e:
            log.exception(
                "gemini_generate",
                "Gemini 生成に失敗しました",
                model=target_model,
            )
            raise AIGenerationError(f"Generation failed: {e}") from e

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
        """Generate text response from prompt with image input."""
        if image_bytes is None and image_uri is None:
            raise ValueError("image_bytes か image_uri のいずれかを指定してください")

        target_model = model or self.model
        try:
            log.debug(
                "gemini_image",
                "Gemini 画像リクエスト",
                image_size=len(image_bytes) if image_bytes else 0,
                image_uri=image_uri,
                mime_type=mime_type,
                model=target_model,
                structured=response_model is not None,
            )

            # Configure generation config
            config_params: GenConfig = {
                "temperature": self.temperature,
                "max_output_tokens": max_tokens or self.max_tokens,
            }
            if response_model:
                config_params["response_mime_type"] = "application/json"
                config_params["response_json_schema"] = (
                    response_model.model_json_schema()
                )

            if system_instruction:
                config_params["system_instruction"] = system_instruction
            if cached_content_name:
                config_params["cached_content"] = cached_content_name

            config = self._types.GenerateContentConfig(**config_params)

            if image_uri:
                image_part = self._types.Part.from_uri(
                    file_uri=image_uri, mime_type=mime_type
                )
            elif image_bytes:
                image_part = self._types.Part.from_bytes(
                    data=image_bytes, mime_type=mime_type
                )
            else:
                image_part = None

            contents = [image_part, prompt] if image_part else [prompt]

            response = await self.client.aio.models.generate_content(
                model=target_model,
                contents=contents,
                config=config,
            )
            self._check_truncation(
                response, target_model, "gemini_image", self.max_tokens
            )

            if response_model:
                try:
                    # Method 1: Use .parsed if available (google-genai SDK 1.0+)
                    if hasattr(response, "parsed") and response.parsed is not None:
                        if isinstance(response.parsed, response_model):
                            return response.parsed
                        if isinstance(response.parsed, dict):
                            return response_model.model_validate(response.parsed)

                    # Method 2: Manual Parse (from .text)
                    text_to_parse = (response.text or "").strip()
                    if text_to_parse.startswith("```json"):
                        text_to_parse = text_to_parse[7:].strip("` \n")
                    elif text_to_parse.startswith("```"):
                        text_to_parse = text_to_parse[3:].strip("` \n")
                    return response_model.model_validate_json(text_to_parse)
                except Exception as parse_err:
                    log.error(
                        "gemini_image",
                        "構造化画像出力のパースに失敗しました",
                        error=str(parse_err),
                    )
                    raise AIGenerationError(
                        f"Failed to parse structured image output: {parse_err}"
                    ) from parse_err

            result = (response.text or "").strip()
            log.debug(
                "gemini_image",
                "Gemini 画像レスポンス",
                response_length=len(result),
            )
            return result

        except Exception as e:
            log.exception(
                "gemini_image",
                "Gemini 画像生成に失敗しました",
                mime_type=mime_type,
            )
            raise AIGenerationError(f"Image analysis failed: {e}") from e

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
        try:
            log.debug(
                "gemini_multi_image",
                "Gemini 複数画像リクエスト",
                image_count=len(images_list),
                model=target_model,
                structured=response_model is not None,
            )

            # Configure generation config
            config_params: GenConfig = {
                "temperature": self.temperature,
                "max_output_tokens": effective_max_tokens,
            }
            if response_model:
                config_params["response_mime_type"] = "application/json"
                config_params["response_json_schema"] = (
                    response_model.model_json_schema()
                )

            if system_instruction:
                config_params["system_instruction"] = system_instruction
            if cached_content_name:
                config_params["cached_content"] = cached_content_name

            config = self._types.GenerateContentConfig(**config_params)

            if cached_content_name:
                contents = [prompt]
            else:
                contents = []
                for img_bytes in images_list:
                    contents.append(
                        self._types.Part.from_bytes(data=img_bytes, mime_type=mime_type)
                    )
                contents.append(prompt)

            response = await self.client.aio.models.generate_content(
                model=target_model,
                contents=contents,
                config=config,
            )
            self._check_truncation(
                response, target_model, "gemini_multi_image", effective_max_tokens
            )

            if response_model:
                try:
                    if hasattr(response, "parsed") and response.parsed is not None:
                        if isinstance(response.parsed, response_model):
                            return response.parsed
                        if isinstance(response.parsed, dict):
                            return response_model.model_validate(response.parsed)
                        raise ValueError(
                            f"Unexpected parsed type: {type(response.parsed)}"
                        )
                    text_to_parse = response.text or ""
                    text_to_parse = text_to_parse.strip()
                    if text_to_parse.startswith("```json"):
                        text_to_parse = text_to_parse[7:].strip("` \n")
                    return response_model.model_validate_json(text_to_parse)
                except Exception as parse_err:
                    log.error(
                        "gemini_multi_image",
                        "構造化複数画像出力のパースに失敗しました",
                        error=str(parse_err),
                    )

                    return response_model.model_validate_json(response.text or "{}")

            return (response.text or "").strip()
        except Exception as e:
            log.exception("gemini_multi_image", "Gemini 複数画像生成に失敗しました")
            raise AIGenerationError(f"Multi-image analysis failed: {e}") from e

    async def generate_with_pdf(
        self,
        prompt: str,
        pdf_bytes: bytes | None = None,
        model: str | None = None,
        cached_content_name: str | None = None,
    ) -> str:
        """Generate text response from prompt with PDF input."""
        target_model = model or self.model
        try:
            log.debug(
                "gemini_pdf",
                "Gemini PDFリクエスト",
                pdf_size=len(pdf_bytes) if pdf_bytes else 0,
                model=target_model,
                cached=cached_content_name is not None,
            )

            config_params: GenConfig = {
                "temperature": self.temperature,
                "max_output_tokens": self.max_tokens,
            }
            if cached_content_name:
                config_params["cached_content"] = cached_content_name
            config = self._types.GenerateContentConfig(**config_params)

            contents = (
                [prompt]
                if cached_content_name
                else [
                    self._types.Part.from_bytes(
                        data=pdf_bytes, mime_type="application/pdf"
                    ),
                    prompt,
                ]
            )

            response = await self.client.aio.models.generate_content(
                model=target_model,
                contents=contents,
                config=config,
            )
            self._check_truncation(
                response, target_model, "gemini_pdf", self.max_tokens
            )
            result = str(response.text or "").strip()
            log.debug(
                "gemini_pdf",
                "Gemini PDFレスポンス",
                response_length=len(result),
            )
            return result

        except Exception as e:
            log.exception(
                "gemini_pdf",
                "Gemini PDF生成に失敗しました",
                pdf_size=len(pdf_bytes) if pdf_bytes else 0,
            )
            raise AIGenerationError(f"PDF analysis failed: {e}") from e

    async def count_tokens(self, contents: Any, model: str | None = None) -> int:
        """Count tokens using Gemini API."""
        target_model = model or self.model
        try:
            resp = await self.client.aio.models.count_tokens(
                model=target_model, contents=contents
            )
            return int(resp.total_tokens or 0)
        except Exception as e:
            log.error("count_tokens", "トークン数のカウントに失敗しました", error=str(e))
            return 0

    async def create_context_cache(
        self,
        model: str,
        contents: Any,
        system_instruction: str | None = None,
        ttl_minutes: int = 60,
    ) -> str:
        """Create a Gemini context cache."""
        try:
            log.info(
                "create_context_cache",
                "Geminiコンテキストキャッシュを作成中",
                model=model,
                ttl_minutes=ttl_minutes,
            )

            # contents can be a list of parts or a single string
            if isinstance(contents, str):
                parts = [self._types.Part.from_text(text=contents)]
            elif isinstance(contents, bytes):
                # Assume PDF if bytes
                parts = [
                    self._types.Part.from_bytes(
                        data=contents, mime_type="application/pdf"
                    )
                ]
            else:
                parts = contents

            cache = await self.client.aio.caches.create(
                model=model,
                config=self._types.CreateCachedContentConfig(
                    contents=parts,
                    system_instruction=system_instruction,
                    ttl=f"{ttl_minutes * 60}s",
                ),
            )
            log.info(
                "create_context_cache",
                "Geminiコンテキストキャッシュを作成しました",
                cache_name=cache.name,
            )

            return cache.name or ""
        except Exception as e:
            log.error(
                "create_context_cache",
                "Geminiコンテキストキャッシュの作成に失敗しました",
                error=str(e),
            )

            raise AIProviderError(f"Cache creation failed: {e}")

    async def delete_context_cache(self, cache_name: str) -> None:
        """Delete a Gemini context cache."""
        try:
            await self.client.aio.caches.delete(name=cache_name)
            log.info(
                "delete_context_cache",
                "Geminiコンテキストキャッシュを削除しました",
                cache_name=cache_name,
            )

        except Exception as e:
            log.error(
                "delete_context_cache",
                "Geminiコンテキストキャッシュの削除に失敗しました",
                cache_name=cache_name,
                error=str(e),
            )


class VertexAIProvider(AIProviderInterface):
    """
    Vertex AI provider implementation using Google GenAI SDK.

    To use Vertex AI, set:
    - AI_PROVIDER=vertex
    - GCP_PROJECT_ID=your-project-id
    - GCP_LOCATION=us-central1
    - GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json (optional)
    """

    def __init__(self):
        # コールドスタート最適化: 初回使用時のみインポート
        from google import genai
        from google.genai import types

        self._types = types

        self.project_id = settings.get("GCP_PROJECT_ID")
        self.location = settings.get("GCP_LOCATION", "us-central1")
        self.model = settings.get("VERTEX_MODEL", "gemini-2.5-flash-lite")

        if not self.project_id:
            log.warning(
                "vertex_init",
                "GCP_PROJECT_ID が設定されていません。デフォルトの認証情報/設定を使用します。",
            )

        # Service Account認証の設定
        credentials_path = settings.get("GOOGLE_APPLICATION_CREDENTIALS")
        if credentials_path and os.path.exists(credentials_path):
            log.info(
                "vertex_init",
                "サービスアカウントの認証情報を使用します",
                path=credentials_path,
            )

            # google.auth.load_credentials_from_fileを使用
            from google.auth import load_credentials_from_file

            credentials, project = load_credentials_from_file(
                credentials_path,
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )

            # プロジェクトIDが環境変数で指定されていない場合、認証情報から取得
            if not self.project_id and project:
                self.project_id = project
                log.info(
                    "vertex_init", "認証情報からプロジェクトIDを取得しました", project=project
                )

            # 認証情報を使用してクライアントを初期化

            # Authenticate using credentials
            self.client = genai.Client(
                vertexai=True,
                project=self.project_id,
                location=self.location,
                credentials=credentials,
            )
        else:
            # デフォルト認証情報を使用（Application Default Credentials）
            log.info("vertex_init", "アプリケーション デフォルト資格情報 (ADC) を使用します")
            self.client = genai.Client(
                vertexai=True,
                project=self.project_id,
                location=self.location,
            )

        self.temperature = float(settings.get("AI_TEMPERATURE", "0.1"))
        self.max_tokens = int(settings.get("AI_MAX_OUTPUT_TOKENS", "1024"))

        log.info(
            "vertex_init",
            "VertexAIProviderを初期化しました",
            project=self.project_id,
            location=self.location,
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

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
        """Generate text response from prompt."""
        target_model = model or self.model
        try:
            # Construct content parts
            # Simplified content construction to fix type errors and match GeminiProvider style
            contents = (
                prompt
                if cached_content_name
                else (f"{context}\n\n{prompt}" if context else prompt)
            )

            # Configure tools
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
                config_params["response_json_schema"] = (
                    response_model.model_json_schema()
                )

            if system_instruction and not cached_content_name:
                config_params["system_instruction"] = system_instruction
            if cached_content_name:
                config_params["cached_content"] = cached_content_name

            config = self._types.GenerateContentConfig(**config_params)

            log.debug(
                "vertex_generate",
                "Vertex 生成リクエスト",
                model=target_model,
                structured=response_model is not None,
            )

            response = await self.client.aio.models.generate_content(
                model=target_model,
                contents=contents,
                config=config,
            )
            self._check_truncation(
                response, target_model, "vertex_generate", self.max_tokens
            )

            if response_model:
                try:
                    if hasattr(response, "parsed") and response.parsed is not None:
                        if isinstance(response.parsed, response_model):
                            return response.parsed
                        if isinstance(response.parsed, dict):
                            return response_model.model_validate(response.parsed)
                        raise ValueError(
                            f"Unexpected parsed type: {type(response.parsed)}"
                        )
                    text_to_parse = response.text or ""
                    return response_model.model_validate_json(text_to_parse)
                except Exception as parse_err:
                    log.error(
                        "vertex_generate",
                        "Vertexからの構造化出力のパースに失敗しました",
                        error=str(parse_err),
                    )

                    text_to_parse = response.text or ""

                    text_to_parse = text_to_parse.strip()
                    if text_to_parse.startswith("```json"):
                        text_to_parse = text_to_parse[7:].strip("` \n")
                    return response_model.model_validate_json(text_to_parse)

            result = str(response.text or "").strip()
            return result

        except Exception as e:
            log.exception("vertex_generate", "Vertex AI 生成に失敗しました")
            raise AIGenerationError(f"Vertex generation failed: {e}") from e

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
        """Generate text response from prompt with image input."""
        if image_bytes is None and image_uri is None:
            raise ValueError("image_bytes か image_uri のいずれかを指定してください")

        target_model = model or self.model
        try:
            if image_uri:
                image_part = self._types.Part.from_uri(
                    file_uri=image_uri, mime_type=mime_type
                )
            elif image_bytes:
                image_part = self._types.Part.from_bytes(
                    data=image_bytes, mime_type=mime_type
                )
            else:
                image_part = None

            contents = [image_part, prompt] if image_part else [prompt]

            config_params: GenConfig = {
                "temperature": self.temperature,
                "max_output_tokens": max_tokens or self.max_tokens,
            }
            if response_model:
                config_params["response_mime_type"] = "application/json"
                # Vertex AI マルチモーダルでは response_json_schema (dict) は
                # 400 INVALID_ARGUMENT になるため response_schema (Pydantic model) を使用
                config_params["response_schema"] = response_model

            if system_instruction:
                config_params["system_instruction"] = system_instruction
            if cached_content_name:
                config_params["cached_content"] = cached_content_name

            config = self._types.GenerateContentConfig(**config_params)

            response = await self.client.aio.models.generate_content(
                model=target_model,
                contents=contents,
                config=config,
            )
            self._check_truncation(
                response, target_model, "vertex_image", self.max_tokens
            )

            if response_model:
                try:
                    if hasattr(response, "parsed") and response.parsed is not None:
                        if isinstance(response.parsed, response_model):
                            return response.parsed
                        if isinstance(response.parsed, dict):
                            return response_model.model_validate(response.parsed)
                        raise ValueError(
                            f"Unexpected parsed type: {type(response.parsed)}"
                        )
                    text_to_parse = response.text or ""
                    return response_model.model_validate_json(text_to_parse)
                except Exception as parse_err:
                    log.error(
                        "vertex_image",
                        "Vertexからの構造化画像出力のパースに失敗しました",
                        error=str(parse_err),
                    )

                    text_to_parse = response.text or ""

                    text_to_parse = text_to_parse.strip()
                    if text_to_parse.startswith("```json"):
                        text_to_parse = text_to_parse[7:].strip("` \n")
                    return response_model.model_validate_json(text_to_parse)

            return (response.text or "").strip()

            return (response.text or "").strip()

        except Exception as e:
            log.exception(
                "vertex_image",
                "Vertex AI 画像生成に失敗しました",
            )
            raise AIGenerationError(f"Vertex image analysis failed: {e}") from e

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
        try:
            if cached_content_name:
                contents = [prompt]
            else:
                contents = []
                for img_bytes in images_list:
                    contents.append(
                        self._types.Part.from_bytes(data=img_bytes, mime_type=mime_type)
                    )
                contents.append(prompt)

            config_params: GenConfig = {
                "temperature": self.temperature,
                "max_output_tokens": effective_max_tokens,
            }
            if response_model:
                config_params["response_mime_type"] = "application/json"
                # Vertex AI マルチモーダルでは response_json_schema (dict) は
                # 400 INVALID_ARGUMENT になるため response_schema (Pydantic model) を使用
                config_params["response_schema"] = response_model

            if system_instruction:
                config_params["system_instruction"] = system_instruction
            if cached_content_name:
                config_params["cached_content"] = cached_content_name

            config = self._types.GenerateContentConfig(**config_params)

            response = await self.client.aio.models.generate_content(
                model=target_model,
                contents=contents,
                config=config,
            )
            self._check_truncation(
                response, target_model, "vertex_multi_image", effective_max_tokens
            )

            if response_model:
                try:
                    if hasattr(response, "parsed") and response.parsed is not None:
                        if isinstance(response.parsed, response_model):
                            return response.parsed
                        if isinstance(response.parsed, dict):
                            return response_model.model_validate(response.parsed)
                        raise ValueError(
                            f"Unexpected parsed type: {type(response.parsed)}"
                        )
                    text_to_parse = (response.text or "").strip()
                    if text_to_parse.startswith("```json"):
                        text_to_parse = text_to_parse[7:].strip("` \n")
                    return response_model.model_validate_json(text_to_parse)
                except Exception as parse_err:
                    log.error(
                        "vertex_multi_image",
                        "Vertexからの構造化複数画像出力のパースに失敗しました",
                        error=str(parse_err),
                    )

                    return response_model.model_validate_json(response.text or "{}")

            return (response.text or "").strip()
        except Exception as e:
            log.exception("vertex_multi_image", "Vertex 複数画像生成に失敗しました")
            raise AIGenerationError(f"Vertex multi-image analysis failed: {e}") from e

    async def generate_with_pdf(
        self,
        prompt: str,
        pdf_bytes: bytes | None = None,
        model: str | None = None,
        cached_content_name: str | None = None,
    ) -> str:
        """Generate text response from prompt with PDF input."""
        target_model = model or self.model
        try:
            contents = (
                [prompt]
                if cached_content_name
                else [
                    self._types.Part.from_bytes(
                        data=pdf_bytes, mime_type="application/pdf"
                    ),
                    prompt,
                ]
            )

            config_params: GenConfig = {
                "temperature": self.temperature,
                "max_output_tokens": self.max_tokens,
            }
            if cached_content_name:
                config_params["cached_content"] = cached_content_name

            config = self._types.GenerateContentConfig(**config_params)

            response = await self.client.aio.models.generate_content(
                model=target_model,
                contents=contents,
                config=config,
            )
            self._check_truncation(
                response, target_model, "vertex_pdf", self.max_tokens
            )
            return str(response.text or "").strip()

        except Exception as e:
            log.exception("vertex_pdf", "Vertex AI PDF 生成に失敗しました")
            raise AIGenerationError(f"Vertex PDF analysis failed: {e}") from e

    async def count_tokens(self, contents: Any, model: str | None = None) -> int:
        """Count tokens using Vertex AI API."""
        target_model = model or self.model
        try:
            resp = await self.client.aio.models.count_tokens(
                model=target_model, contents=contents
            )
            return int(resp.total_tokens or 0)
        except Exception as e:
            log.error(
                "count_tokens_vertex", "トークン数のカウントに失敗しました (Vertex)", error=str(e)
            )
            return 0

    async def create_context_cache(
        self,
        model: str,
        contents: Any,
        system_instruction: str | None = None,
        ttl_minutes: int = 60,
    ) -> str:
        """Create a Vertex AI context cache."""
        # Vertex AI also supports caching but through slightly different API/params in genai SDK.
        # This implementation uses the Gemini direct API for caching.
        try:
            log.info(
                "create_context_cache_vertex",
                "Vertexコンテキストキャッシュを作成中",
                model=model,
            )

            if isinstance(contents, str):
                parts = [self._types.Part.from_text(text=contents)]
            elif isinstance(contents, bytes):
                parts = [
                    self._types.Part.from_bytes(
                        data=contents, mime_type="application/pdf"
                    )
                ]
            else:
                parts = contents

            cache = await self.client.aio.caches.create(
                model=model,
                config=self._types.CreateCachedContentConfig(
                    contents=parts,
                    system_instruction=system_instruction,
                    ttl=f"{ttl_minutes * 60}s",
                ),
            )
            return str(cache.name or "")
        except Exception as e:
            log.error(
                "create_context_cache_vertex",
                "Vertexキャッシュの作成に失敗しました",
                error=str(e),
            )

            raise AIProviderError(f"Vertex cache creation failed: {e}")

    async def delete_context_cache(self, cache_name: str) -> None:
        """Delete a Vertex AI context cache."""
        try:
            await self.client.aio.caches.delete(name=cache_name)
        except Exception as e:
            log.error(
                "delete_context_cache_vertex",
                "Vertexキャッシュの削除に失敗しました",
                error=str(e),
            )


# Singleton instance cache
_ai_provider_instance: AIProviderInterface | None = None


def get_ai_provider() -> AIProviderInterface:
    """
    Factory function to get the configured AI provider (singleton).

    Set AI_PROVIDER environment variable:
    - "gemini" (default): Use Gemini API directly
    - "vertex": Use Vertex AI (requires GCP setup)
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

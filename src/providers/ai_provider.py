import os
from abc import ABC, abstractmethod
from typing import Any, Type

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel

from src.logger import logger

load_dotenv()


class AIProviderError(Exception):
    """Base exception for AI Provider errors."""

    pass


class AIGenerationError(AIProviderError):
    """Exception for generation failures."""

    pass


class AIProviderInterface(ABC):
    """Abstract interface for AI providers."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        context: str = "",
        model: str | None = None,
        enable_search: bool = False,
        response_model: Type[BaseModel] | None = None,
        system_instruction: str | None = None,
    ) -> Any:
        """Generate text or structured response from prompt."""
        ...

    @abstractmethod
    async def generate_with_image(
        self,
        prompt: str,
        image_bytes: bytes,
        mime_type: str = "image/png",
        model: str | None = None,
        response_model: Type[BaseModel] | None = None,
    ) -> Any:
        """Generate text or structured response from prompt with image input."""
        ...

    @abstractmethod
    async def generate_with_pdf(
        self, prompt: str, pdf_bytes: bytes, model: str | None = None
    ) -> str:
        """Generate text response from prompt with PDF input."""
        ...

    @abstractmethod
    async def count_tokens(self, contents: Any, model: str | None = None) -> int:
        """Count tokens for the given contents."""
        ...


class GeminiProvider(AIProviderInterface):
    """Gemini API provider implementation."""

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        self.client = genai.Client(api_key=api_key, vertexai=False)
        self.model = os.getenv("MODEL_OCR", "gemini-2.0-flash")
        logger.info(f"GeminiProvider initialized with model: {self.model}")

    async def generate(
        self,
        prompt: str,
        context: str = "",
        model: str | None = None,
        enable_search: bool = False,
        response_model: Type[BaseModel] | None = None,
        system_instruction: str | None = None,
    ) -> Any:
        """Generate text response from prompt, optionally as structured data."""
        target_model = model or self.model
        try:
            full_prompt = f"{context}\n\n{prompt}" if context else prompt
            logger.debug(
                "Gemini generate request",
                extra={
                    "prompt_length": len(full_prompt),
                    "model": target_model,
                    "search": enable_search,
                    "structured": response_model is not None,
                },
            )

            # Configure tools
            tools = None
            if enable_search:
                tools = [types.Tool(google_search=types.GoogleSearch())]

            # Configure generation config
            config_params: dict[str, Any] = {}
            if tools:
                config_params["tools"] = tools
            if response_model:
                config_params["response_mime_type"] = "application/json"
                config_params["response_schema"] = response_model

            if system_instruction:
                config_params["system_instruction"] = system_instruction

            config = types.GenerateContentConfig(**config_params) if config_params else None

            response = await self.client.aio.models.generate_content(
                model=target_model,
                contents=full_prompt,
                config=config,
            )

            if response_model:
                # If parsed is available in the SDK version and it works for Pydantic
                # Otherwise we might need to manual parse response.text
                try:
                    # google-genai SDK 1.0.0+ supports .parsed for structured output
                    if hasattr(response, "parsed") and response.parsed is not None:
                        return response.parsed

                    # Fallback to manual parsing if .parsed is not what we expect
                    return response_model.model_validate_json(response.text or "")
                except Exception as parse_err:
                    logger.error(f"Failed to parse structured output: {parse_err}")
                    # If it's wrapped in markdown, try to strip
                    text_to_parse = response.text or ""
                    text_to_parse = text_to_parse.strip()
                    if text_to_parse.startswith("```json"):
                        text_to_parse = text_to_parse[7:].strip("` \n")
                    elif text_to_parse.startswith("```"):
                        text_to_parse = text_to_parse[3:].strip("` \n")
                    return response_model.model_validate_json(text_to_parse)

            result = (response.text or "").strip()
            logger.debug(
                "Gemini generate response",
                extra={"response_length": len(result)},
            )
            return result
        except Exception as e:
            logger.exception(
                "Gemini generation failed",
                extra={"error": str(e), "model": target_model},
            )
            raise AIGenerationError(f"Generation failed: {e}") from e

    async def generate_with_image(
        self,
        prompt: str,
        image_bytes: bytes,
        mime_type: str = "image/png",
        model: str | None = None,
        response_model: Type[BaseModel] | None = None,
    ) -> Any:
        """Generate text response from prompt with image input."""
        target_model = model or self.model
        try:
            logger.debug(
                "Gemini image request",
                extra={
                    "image_size": len(image_bytes),
                    "mime_type": mime_type,
                    "model": target_model,
                    "structured": response_model is not None,
                },
            )

            # Configure generation config
            config_params: dict[str, Any] = {}
            if response_model:
                config_params["response_mime_type"] = "application/json"
                config_params["response_schema"] = response_model

            config = types.GenerateContentConfig(**config_params) if config_params else None

            response = await self.client.aio.models.generate_content(
                model=target_model,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    prompt,
                ],
                config=config,
            )

            if response_model:
                try:
                    if hasattr(response, "parsed") and response.parsed is not None:
                        return response.parsed
                    text_to_parse = response.text or ""
                    return response_model.model_validate_json(text_to_parse)
                except Exception as parse_err:
                    logger.error(f"Failed to parse structured image output: {parse_err}")
                    text_to_parse = response.text or ""
                    text_to_parse = text_to_parse.strip()
                    if text_to_parse.startswith("```json"):
                        text_to_parse = text_to_parse[7:].strip("` \n")
                    return response_model.model_validate_json(text_to_parse)

            result = (response.text or "").strip()
            logger.debug(
                "Gemini image response",
                extra={"response_length": len(result)},
            )
            return result
        except Exception as e:
            logger.exception(
                "Gemini image generation failed",
                extra={"error": str(e), "mime_type": mime_type},
            )
            raise AIGenerationError(f"Image analysis failed: {e}") from e

    async def generate_with_pdf(
        self, prompt: str, pdf_bytes: bytes, model: str | None = None
    ) -> str:
        """Generate text response from prompt with PDF input."""
        target_model = model or self.model
        try:
            logger.debug(
                "Gemini PDF request",
                extra={"pdf_size": len(pdf_bytes), "model": target_model},
            )
            response = await self.client.aio.models.generate_content(
                model=target_model,
                contents=[
                    types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                    prompt,
                ],
            )
            result = (response.text or "").strip()
            logger.debug(
                "Gemini PDF response",
                extra={"response_length": len(result)},
            )
            return result
        except Exception as e:
            logger.exception(
                "Gemini PDF generation failed",
                extra={"error": str(e), "pdf_size": len(pdf_bytes)},
            )
            raise AIGenerationError(f"PDF analysis failed: {e}") from e

    async def count_tokens(self, contents: Any, model: str | None = None) -> int:
        """Count tokens using Gemini API."""
        target_model = model or self.model
        try:
            resp = await self.client.aio.models.count_tokens(model=target_model, contents=contents)
            return int(resp.total_tokens or 0)
        except Exception as e:
            logger.error(f"Token counting failed: {e}")
            return 0


class VertexAIProvider(AIProviderInterface):
    """
    Vertex AI provider implementation using Google GenAI SDK.

    To use Vertex AI, set:
    - AI_PROVIDER=vertex
    - GCP_PROJECT_ID=your-project-id
    - GCP_LOCATION=us-central1
    """

    def __init__(self):
        self.project_id = os.getenv("GCP_PROJECT_ID")
        self.location = os.getenv("GCP_LOCATION", "us-central1")
        self.model = os.getenv("VERTEX_MODEL", "gemini-2.0-flash-lite-001")

        if not self.project_id:
            # Fallback or strict error? Let's check env or assume ADC might work without explicit project in some cases,
            # but usually project is needed for Vertex init in this SDK style.
            # However, genai.Client might auto-detect. Let's warn if missing.
            logger.warning(
                "GCP_PROJECT_ID not set for VertexAIProvider. Relying on default credentials/config."
            )

        self.client = genai.Client(
            vertexai=True,
            project=self.project_id,
            location=self.location,
        )
        logger.info(
            f"VertexAIProvider initialized: project={self.project_id}, location={self.location}, model={self.model}"
        )

    async def generate(
        self,
        prompt: str,
        context: str = "",
        model: str | None = None,
        enable_search: bool = False,
        response_model: Type[BaseModel] | None = None,
        system_instruction: str | None = None,
    ) -> Any:
        """Generate text response from prompt."""
        target_model = model or self.model
        try:
            # Construct content parts
            # Simplified content construction to fix type errors and match GeminiProvider style
            contents = f"{context}\n\n{prompt}" if context else prompt

            # Configure tools
            tools = None
            if enable_search:
                tools = [types.Tool(google_search=types.GoogleSearch())]

            config_params: dict[str, Any] = {
                "temperature": 0.2,
                "top_k": 40,
                "max_output_tokens": 8192,
            }
            if tools:
                config_params["tools"] = tools
            if response_model:
                config_params["response_mime_type"] = "application/json"
                config_params["response_schema"] = response_model

            if system_instruction:
                config_params["system_instruction"] = system_instruction

            config = types.GenerateContentConfig(**config_params)

            logger.debug(
                "Vertex generate request",
                extra={"model": target_model, "structured": response_model is not None},
            )

            response = await self.client.aio.models.generate_content(
                model=target_model,
                contents=contents,
                config=config,
            )

            if response_model:
                try:
                    if hasattr(response, "parsed") and response.parsed is not None:
                        return response.parsed
                    text_to_parse = response.text or ""
                    return response_model.model_validate_json(text_to_parse)
                except Exception as parse_err:
                    logger.error(f"Failed to parse structured output from Vertex: {parse_err}")
                    text_to_parse = response.text or ""
                    text_to_parse = text_to_parse.strip()
                    if text_to_parse.startswith("```json"):
                        text_to_parse = text_to_parse[7:].strip("` \n")
                    return response_model.model_validate_json(text_to_parse)

            result = (response.text or "").strip()
            return result

        except Exception as e:
            logger.exception("Vertex AI generation failed", extra={"error": str(e)})
            raise AIGenerationError(f"Vertex generation failed: {e}") from e

    async def generate_with_image(
        self,
        prompt: str,
        image_bytes: bytes,
        mime_type: str = "image/png",
        model: str | None = None,
        response_model: Type[BaseModel] | None = None,
    ) -> Any:
        """Generate text response from prompt with image input."""
        target_model = model or self.model
        try:
            contents = [
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                prompt,
            ]

            config_params: dict[str, Any] = {"temperature": 0.2, "max_output_tokens": 8192}
            if response_model:
                config_params["response_mime_type"] = "application/json"
                config_params["response_schema"] = response_model

            config = types.GenerateContentConfig(**config_params)

            response = await self.client.aio.models.generate_content(
                model=target_model,
                contents=contents,
                config=config,
            )

            if response_model:
                try:
                    if hasattr(response, "parsed") and response.parsed is not None:
                        return response.parsed
                    text_to_parse = response.text or ""
                    return response_model.model_validate_json(text_to_parse)
                except Exception as parse_err:
                    logger.error(
                        f"Failed to parse structured image output from Vertex: {parse_err}"
                    )
                    text_to_parse = response.text or ""
                    text_to_parse = text_to_parse.strip()
                    if text_to_parse.startswith("```json"):
                        text_to_parse = text_to_parse[7:].strip("` \n")
                    return response_model.model_validate_json(text_to_parse)

            return (response.text or "").strip()

        except Exception as e:
            logger.exception("Vertex AI image generation failed", extra={"error": str(e)})
            raise AIGenerationError(f"Vertex image analysis failed: {e}") from e

    async def generate_with_pdf(
        self, prompt: str, pdf_bytes: bytes, model: str | None = None
    ) -> str:
        """Generate text response from prompt with PDF input."""
        target_model = model or self.model
        try:
            contents = [
                types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                prompt,
            ]

            config = types.GenerateContentConfig(temperature=0.2, max_output_tokens=8192)

            response = await self.client.aio.models.generate_content(
                model=target_model,
                contents=contents,
                config=config,
            )
            return (response.text or "").strip()

        except Exception as e:
            logger.exception("Vertex AI PDF generation failed", extra={"error": str(e)})
            raise AIGenerationError(f"Vertex PDF analysis failed: {e}") from e

    async def count_tokens(self, contents: Any, model: str | None = None) -> int:
        """Count tokens using Vertex AI API."""
        target_model = model or self.model
        try:
            resp = await self.client.aio.models.count_tokens(model=target_model, contents=contents)
            return int(resp.total_tokens or 0)
        except Exception as e:
            logger.error(f"Token counting failed (Vertex): {e}")
            return 0


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

    provider_type = os.getenv("AI_PROVIDER", "gemini").lower()

    if provider_type == "vertex":
        _ai_provider_instance = VertexAIProvider()
    else:
        _ai_provider_instance = GeminiProvider()

    return _ai_provider_instance

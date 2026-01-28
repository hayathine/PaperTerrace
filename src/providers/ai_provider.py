"""
AI Provider abstraction layer.
Supports Gemini API (current) and Vertex AI (future GCP deployment).
"""

import os
from abc import ABC, abstractmethod

from dotenv import load_dotenv
from google import genai
from google.genai import types

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
    async def generate(self, prompt: str, context: str = "", model: str | None = None) -> str:
        """Generate text response from prompt."""
        ...

    @abstractmethod
    async def generate_with_image(
        self,
        prompt: str,
        image_bytes: bytes,
        mime_type: str = "image/png",
        model: str | None = None,
    ) -> str:
        """Generate text response from prompt with image input."""
        ...

    @abstractmethod
    async def generate_with_pdf(
        self, prompt: str, pdf_bytes: bytes, model: str | None = None
    ) -> str:
        """Generate text response from prompt with PDF input."""
        ...


class GeminiProvider(AIProviderInterface):
    """Gemini API provider implementation."""

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        self.client = genai.Client(api_key=api_key)
        self.model = os.getenv("OCR_MODEL", "gemini-1.5-flash")
        logger.info(f"GeminiProvider initialized with model: {self.model}")

    async def generate(self, prompt: str, context: str = "", model: str | None = None) -> str:
        """Generate text response from prompt."""
        target_model = model or self.model
        try:
            full_prompt = f"{context}\n\n{prompt}" if context else prompt
            logger.debug(
                "Gemini generate request",
                extra={"prompt_length": len(full_prompt), "model": target_model},
            )
            response = self.client.models.generate_content(
                model=target_model,
                contents=full_prompt,
            )
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
            raise AIGenerationError(f"Text generation failed: {e}") from e

    async def generate_with_image(
        self,
        prompt: str,
        image_bytes: bytes,
        mime_type: str = "image/png",
        model: str | None = None,
    ) -> str:
        """Generate text response from prompt with image input."""
        target_model = model or self.model
        try:
            logger.debug(
                "Gemini image request",
                extra={
                    "image_size": len(image_bytes),
                    "mime_type": mime_type,
                    "model": target_model,
                },
            )
            response = self.client.models.generate_content(
                model=target_model,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    prompt,
                ],
            )
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
            response = self.client.models.generate_content(
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

    async def generate(self, prompt: str, context: str = "", model: str | None = None) -> str:
        """Generate text response from prompt."""
        target_model = model or self.model
        try:
            # Construct content parts
            parts = [types.Part.from_text(text=prompt)]
            if context:
                # Prepend context as a separate part or combined text?
                # Combined is usually safer for pure text models, but parts are fine too.
                # Let's combine for simplicity unless context is huge.
                parts = [types.Part.from_text(text=f"{context}\n\n{prompt}")]

            contents = [types.Content(role="user", parts=parts)]

            config = types.GenerateContentConfig(
                temperature=0.2,  # Low temp for factual tasks
                top_k=40,
                max_output_tokens=8192,
            )

            logger.debug(
                "Vertex generate request",
                extra={"model": target_model},
            )

            # Note: The client methods are synchronous in the basic SDK example provided.
            # If we want async, we might need run_in_executor or check if async_generate_content exists.
            # The google-genai package (v0.x) often has async methods or we wrap sync ones.
            # Providing example code uses synchronous `client.models.generate_content`.
            # We will wrap it in a thread for now to keep our interface async.
            import asyncio

            loop = asyncio.get_running_loop()

            def _call_vertex():
                return self.client.models.generate_content(
                    model=target_model,
                    contents=contents,
                    config=config,
                )

            response = await loop.run_in_executor(None, _call_vertex)

            result = (response.text or "").strip()
            return result

        except Exception as e:
            logger.exception("Vertex AI generation failed", extra={"error": str(e)})
            raise AIGenerationError(f"Vertex text generation failed: {e}") from e

    async def generate_with_image(
        self,
        prompt: str,
        image_bytes: bytes,
        mime_type: str = "image/png",
        model: str | None = None,
    ) -> str:
        """Generate text response from prompt with image input."""
        target_model = model or self.model
        try:
            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                        types.Part.from_text(text=prompt),
                    ],
                )
            ]

            config = types.GenerateContentConfig(temperature=0.2, max_output_tokens=8192)

            import asyncio

            loop = asyncio.get_running_loop()

            def _call_vertex():
                return self.client.models.generate_content(
                    model=target_model,
                    contents=contents,
                    config=config,
                )

            response = await loop.run_in_executor(None, _call_vertex)
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
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                        types.Part.from_text(text=prompt),
                    ],
                )
            ]

            config = types.GenerateContentConfig(temperature=0.2, max_output_tokens=8192)

            import asyncio

            loop = asyncio.get_running_loop()

            def _call_vertex():
                return self.client.models.generate_content(
                    model=target_model,
                    contents=contents,
                    config=config,
                )

            response = await loop.run_in_executor(None, _call_vertex)
            return (response.text or "").strip()

        except Exception as e:
            logger.exception("Vertex AI PDF generation failed", extra={"error": str(e)})
            raise AIGenerationError(f"Vertex PDF analysis failed: {e}") from e


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

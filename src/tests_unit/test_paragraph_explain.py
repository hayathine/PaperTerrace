import os
import unittest
from unittest.mock import AsyncMock, patch

from src.features.paragraph_explain import ParagraphExplainService


class TestParagraphExplainService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # AIProvider のモック
        self.mock_provider_patcher = patch("src.features.paragraph_explain.get_ai_provider")
        self.mock_get_provider = self.mock_provider_patcher.start()
        self.mock_provider = AsyncMock()
        self.mock_get_provider.return_value = self.mock_provider

    async def asyncTearDown(self):
        self.mock_provider_patcher.stop()

    async def test_explain_uses_correct_model(self):
        """environment variable MODEL_PARAGRAPH should determine the model used."""
        test_model = "test-model-v1"
        with patch.dict(os.environ, {"MODEL_PARAGRAPH": test_model}):
            service = ParagraphExplainService()
            self.assertEqual(service.model, test_model)

            # Mock generate response
            self.mock_provider.generate.return_value = "Detailed explanation"

            await service.explain("Test paragraph", lang="en")

            # Verify generate was called with correct model and English prompt logic
            args, kwargs = self.mock_provider.generate.call_args
            prompt = args[0]
            self.assertIn("Please analyze and explain", prompt)
            self.assertIn("in English", prompt)
            self.assertEqual(kwargs["model"], test_model)

    async def test_explain_terminology(self):
        """explain_terminology should accept lang and return parsed JSON."""
        service = ParagraphExplainService()

        # Mock JSON response
        mock_json_response = """
        ```json
        [
            {"term": "AI", "explanation": "Artificial Intelligence", "importance": "high"}
        ]
        ```
        """
        self.mock_provider.generate.return_value = mock_json_response

        result = await service.explain_terminology("Paragraph with AI", lang="en")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["term"], "AI")

        # Verify call
        args, kwargs = self.mock_provider.generate.call_args
        self.assertEqual(kwargs["model"], service.model)


if __name__ == "__main__":
    unittest.main()

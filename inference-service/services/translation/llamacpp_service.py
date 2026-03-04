import asyncio
import logging
import os
import re
import types
from typing import Any, Optional

import dspy
from llama_cpp import Llama

logger = logging.getLogger(__name__)


class LlamaCppTranslationService:
    """
    llama-cpp-python を利用した高度な翻訳サービス
    Qwen3 30B などの GGUF モデルを使用して、文脈に応じた翻訳と解説を提供します。
    """

    def __init__(self):
        self.llm: Optional[Llama] = None
        # ローカルパスが優先される設定
        self.model_path = os.getenv("LLAMACPP_MODEL_PATH")

        self.n_ctx = int(os.getenv("LLAMACPP_CTX_SIZE", "1024"))
        # 安全性のため、物理コア数(6)より少ないスレッド数(4)をデフォルトに設定します。
        self.n_threads = int(os.getenv("LLAMACPP_THREADS", "4"))
        # Batch size controls peak memory during prompt evaluation.
        # Default reduced from 512 to 64 to prevent OOM on ~10GB Qwen3-30B model.
        self.n_batch = int(os.getenv("LLAMACPP_BATCH_SIZE", "512"))
        self.n_gpu_layers = int(
            os.getenv("LLAMACPP_GPU_LAYERS", "0")
        )  # CPU実行をデフォルトに
        self.use_mlock = os.getenv("LLAMACPP_USE_MLOCK", "false").lower() == "true"
        # mmap allows the model to be loaded from disk on demand, reducing initial RAM usage.
        self.use_mmap = os.getenv("LLAMACPP_USE_MMAP", "true").lower() == "true"
        self.max_tokens = int(os.getenv("LLAMACPP_MAX_TOKENS", "2048"))
        logger.info(f"Llama-cpp モデルの初期化設定: {self.__dict__}")

    async def initialize(self):
        """モデルの初期化。アプリケーション起動時に1度だけ呼び出されます。

        排他制御は呼び出し元（main.py の ensure_initialized）が担保するため、
        このメソッド自体は冪等性チェックのみ行います。
        """
        if self.llm is not None:
            logger.debug("Llama-cpp モデルは既に初期化済みです。スキップします。")
            return

        logger.info("Llama-cpp モデルの初期化を開始します...")

        try:
            loop = asyncio.get_running_loop()

            # ローカルパスから読み込みます
            if self.model_path and os.path.exists(self.model_path):
                logger.info(f"ローカルパスから読み込みます: {self.model_path}")
                self.llm = await loop.run_in_executor(
                    None,
                    lambda: Llama(
                        model_path=self.model_path,
                        n_ctx=self.n_ctx,
                        n_threads=self.n_threads,
                        n_batch=self.n_batch,
                        n_gpu_layers=self.n_gpu_layers,
                        use_mlock=self.use_mlock,
                        use_mmap=self.use_mmap,
                    ),
                )
            else:
                logger.error(
                    f"モデルが見つかりません: {self.model_path or 'パス未設定'}"
                )
                raise FileNotFoundError(
                    f"Model path not found or invalid: {self.model_path}"
                )

            logger.info("Llama-cpp モデルの読み込みが完了しました。")
        except Exception as e:
            logger.error(f"Llama-cpp モデルの初期化中にエラーが発生しました: {e}")
            if os.getenv("DEV_MODE", "false").lower() == "true":
                logger.warning("開発モードのため継続します（推論時にエラーになります）")
                return
            raise RuntimeError(f"Failed to load LLM: {e}")

    async def translate_with_llamacpp(
        self, original_word: str, paper_context: str, lang_name: str = "Japanese"
    ) -> str:
        """
        論文の文脈を考慮した高度な翻訳を実行します。
        DSPyを用いてプロンプト構築と実行を行います。
        """
        if self.llm is None:
            # initialize() は起動時に ensure_initialized() から1度だけ呼ばれる前提。
            # ここに到達した場合は起動シーケンスの異常を示す。
            logger.error(
                "LLM が未初期化の状態で翻訳が要求されました。起動処理を確認してください。"
            )
            return "Error: LLM service is not initialized."

        from common.dspy.signatures import ContextAwareTranslation

        class InMemoryLlama(dspy.BaseLM):
            """DSPy 3.x 互換のインメモリLlamaラッパー。

            DSPy 3.x では BaseLM.forward() を実装し、OpenAI 互換レスポンス形式を返す必要がある。
            __call__ は BaseLM が管理するため、ここでは forward() のみ実装する。
            """

            def __init__(self, llm_instance: Any, max_tokens: int):
                super().__init__(
                    model="local-llama", temperature=0.3, max_tokens=max_tokens
                )
                self.llm_instance = llm_instance
                self._max_tokens = max_tokens

            def forward(
                self,
                prompt: str | None = None,
                messages: list[dict] | None = None,
                **kwargs,
            ) -> Any:
                # Use messages if provided by ChatAdapter, otherwise fallback to wrapping prompt
                chat_messages = messages or [{"role": "user", "content": prompt or ""}]

                logger.debug(f"LLM 推論開始: messages_count={len(chat_messages)}")
                if len(chat_messages) > 0:
                    last_msg = chat_messages[-1]["content"]
                    logger.debug(f"LLM 最終プロンプト: {last_msg[:500]}...")

                logger.debug("llama-cpp-python 推論実行中 (create_chat_completion)...")
                raw = self.llm_instance.create_chat_completion(
                    messages=chat_messages,
                    temperature=kwargs.get("temperature", 0.3),
                    max_tokens=kwargs.get("max_tokens", self._max_tokens),
                )
                logger.debug("llama-cpp-python 推論が正常に終了しました。")

                # Qwen3 thinking models prepend <think>...</think> blocks.
                # Strip them before passing the text to DSPy's output parser.
                text = raw["choices"][0]["message"]["content"]
                logger.debug(
                    f"LLM 生レスポンス取得 (文字数={len(text)}): {text[:500]}..."
                )
                text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

                # DSPy BaseLM._process_completion requires an OpenAI-like response object
                # with attribute access (response.choices, response.usage, response.model).
                usage = raw.get(
                    "usage",
                    {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                )
                message_ns = types.SimpleNamespace(content=text, role="assistant")
                choice_ns = types.SimpleNamespace(
                    message=message_ns,
                    finish_reason="stop",
                    index=0,
                )
                return types.SimpleNamespace(
                    choices=[choice_ns],
                    usage=usage,
                    model="local-llama",
                )

        try:
            logger.info(
                f"LLM 翻訳実行開始: word='{original_word[:50]}', lang='{lang_name}', context_len={len(paper_context)}"
            )
            import time

            start_time = time.time()
            loop = asyncio.get_running_loop()

            # DSPy predict can be blocking, so we run it in executor.
            # Use dspy.context() instead of dspy.settings.configure() because
            # the latter modifies global state and DSPy forbids it from non-main threads.
            def _run_dspy():
                logger.debug("DSPy 推論スレッド開始 (executor内)")
                lm = InMemoryLlama(self.llm, self.max_tokens)
                # Use ChatAdapter to properly handle system prompts from Signatures
                with dspy.context(lm=lm, adapter=dspy.ChatAdapter()):
                    logger.debug("DSPy predictor 初期化中...")
                    logger.debug(
                        f"コンテキスト確認: paper_context 先頭200文字 = {paper_context[:200]!r}"
                    )
                    predictor = dspy.Predict(ContextAwareTranslation)
                    logger.debug("DSPy predictor 実行中...")
                    prediction = predictor(
                        paper_context=paper_context,
                        target_word=original_word,
                        lang_name=lang_name,
                    )
                    logger.debug("DSPy predictor 実行完了")
                    return prediction.translation_and_explanation

            logger.debug("executor に翻訳タスクを投入します...")
            result = await loop.run_in_executor(None, _run_dspy)
            elapsed = time.time() - start_time
            logger.info(
                f"LLM 翻訳が正常に完了しました。経過時間: {elapsed:.2f}s, 結果文字数: {len(result)}"
            )
            return result.strip()

        except Exception as e:
            logger.error(f"LLM 推論エラー: {e}")
            return f"Translation error occurred: {str(e)}"

    async def cleanup(self):
        """リソースを解放します。"""
        if self.llm:
            # llama-cpp-python 側に明示的な close はないが、参照を消しておく
            self.llm = None
            logger.info("Llama-cpp サービスをクリーンアップしました。")

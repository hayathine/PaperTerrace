import asyncio
import logging
import os
from typing import Optional

from llama_cpp import Llama

logger = logging.getLogger(__name__)


class LlamaCppTranslationService:
    """
    llama-cpp-python を利用した高度な翻訳サービス
    Qwen3 30B などの GGUF モデルを使用して、文脈に応じた翻訳と解説を提供します。
    """

    def __init__(self):
        self.llm: Optional[Llama] = None
        # 環境変数から設定を取得
        # デフォルトモデル: byteshape/Qwen3-30B-A3B-Instruct-2507-GGUF
        # ファイル名: Q3_K_S-2.66bow (ユーザー指定)
        self.repo_id = os.getenv(
            "LLAMACPP_REPO_ID", "byteshape/Qwen3-30B-A3B-Instruct-2507-GGUF"
        )
        self.filename = os.getenv(
            "LLAMACPP_MODEL_NAME", "Q3_K_S-2.66bow.gguf"
        )  # 本来は .gguf が付くはずだがユーザー指定に合わせる

        # ローカルパスが優先される設定
        self.model_path = os.getenv("LLAMACPP_MODEL_PATH")

        self.n_ctx = int(os.getenv("LLAMACPP_CTX_SIZE", "4096"))
        # 安全性のため、物理コア数(6)より少ないスレッド数(4)をデフォルトに設定します。
        # これにより並列処理による不可解なクラッシュのリスクを軽減します。
        self.n_threads = int(os.getenv("LLAMACPP_THREADS", "4"))
        self.n_batch = int(os.getenv("LLAMACPP_BATCH_SIZE", "512"))
        self.n_gpu_layers = int(
            os.getenv("LLAMACPP_GPU_LAYERS", "0")
        )  # CPU実行をデフォルトに
        # モデルが1GB程度と軽量なため、メモリにロック (mlock) してスワップを防ぎ
        # 常に高速なレスポンスが維持されるようにします。
        self.use_mlock = os.getenv("LLAMACPP_USE_MLOCK", "true").lower() == "true"

    async def initialize(self):
        """モデルの初期化。初回呼び出し時に実行されます。"""
        if self.llm is not None:
            return

        async with asyncio.Lock():  # 二重初期化防止
            if self.llm is not None:
                return

            logger.info("Llama-cpp モデルの初期化を開始します...")

            try:
                loop = asyncio.get_event_loop()

                # Hugging Face からのダウンロードまたはローカル読み込み
                # Llama.from_pretrained は重い処理なので executor で実行
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
                        ),
                    )
                elif os.getenv("LLAMACPP_ALLOW_DOWNLOAD", "false").lower() == "true":
                    logger.info(
                        f"Hugging Face Hub から読み込みます: {self.repo_id} ({self.filename})"
                    )
                    # llama-cpp-python の from_pretrained を使用
                    target_filename = (
                        self.filename
                        if self.filename.endswith(".gguf")
                        else f"{self.filename}.gguf"
                    )

                    self.llm = await loop.run_in_executor(
                        None,
                        lambda: Llama.from_pretrained(
                            repo_id=self.repo_id,
                            filename=target_filename,
                            n_ctx=self.n_ctx,
                            n_threads=self.n_threads,
                            n_batch=self.n_batch,
                            n_gpu_layers=self.n_gpu_layers,
                            use_mlock=self.use_mlock,
                            verbose=False,
                        ),
                    )
                else:
                    logger.warning(
                        "LLAMACPP_MODEL_PATH が設定されていないか見つかりません。ダウンロードも許可されていないため、LLM初期化をスキップします。"
                    )
                    return

                logger.info("Llama-cpp モデルの読み込みが完了しました。")
            except Exception as e:
                logger.error(f"Llama-cpp モデルの初期化中にエラーが発生しました: {e}")
                if os.getenv("DEV_MODE", "false").lower() == "true":
                    logger.warning(
                        "開発モードのため継続します（推論時にエラーになります）"
                    )
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
            await self.initialize()

        if self.llm is None:
            return "Error: LLM service is not initialized."

        import dspy

        from common.dspy.signatures import ContextAwareTranslation

        class InMemoryLlama(dspy.LM):
            """DSPy 3.x 互換のインメモリLlamaラッパー"""

            def __init__(self, llm_instance):
                super().__init__("local-llama")
                self.llm_instance = llm_instance
                self.kwargs = {"temperature": 0.3, "max_tokens": 1024}
                self.history = []

            def __call__(
                self,
                prompt: str | None = None,
                messages: list[dict] | None = None,
                **kwargs,
            ) -> list[str]:
                # DSPy 3.x は messages= キーワード引数でLMを呼び出す
                if messages:
                    chat_messages = [
                        {
                            "role": "system",
                            "content": "You are an expert academic research assistant. Never output markdown formatting for JSON, act directly.",
                        },
                        *messages,
                    ]
                else:
                    chat_messages = [
                        {
                            "role": "system",
                            "content": "You are an expert academic research assistant. Never output markdown formatting for JSON, act directly.",
                        },
                        {"role": "user", "content": prompt or ""},
                    ]

                response = self.llm_instance.create_chat_completion(
                    messages=chat_messages,
                    temperature=kwargs.get("temperature", self.kwargs["temperature"]),
                    max_tokens=kwargs.get("max_tokens", self.kwargs["max_tokens"]),
                )
                text = response["choices"][0]["message"]["content"]
                self.history.append({"messages": chat_messages, "response": text})
                return [text]

        logger.info(f"LLM 翻訳実行中... (Word: {original_word[:20]}...)")

        try:
            loop = asyncio.get_event_loop()

            # DSPy predict can be blocking, so we run it in executor.
            def _run_dspy():
                dspy.settings.configure(lm=InMemoryLlama(self.llm))
                predictor = dspy.Predict(ContextAwareTranslation)
                prediction = predictor(
                    paper_context=paper_context,
                    target_text=original_word,
                    lang_name=lang_name,
                )
                return prediction.translation_and_explanation

            result = await loop.run_in_executor(None, _run_dspy)
            logger.info("LLM 翻訳が完了しました。")
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

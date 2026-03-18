import asyncio
import logging
import os
import re
from typing import Optional

from llama_cpp import Llama

from common import settings

logger = logging.getLogger(__name__)


class LlamaBusyError(RuntimeError):
    """llama-cpp が別のリクエストを処理中に新規リクエストが来た場合に送出される。"""


class LlamaCppTranslationService:
    """
    llama-cpp-python を利用した高度な翻訳サービス
    Qwen3 30B などの GGUF モデルを使用して、文脈に応じた翻訳と解説を提供します。
    """

    def __init__(self):
        self.llm: Optional[Llama] = None
        # ローカルパスが優先される設定
        self.model_path = settings.get("LLAMACPP_MODEL_PATH")

        self.n_ctx = int(settings.get("LLAMACPP_CTX_SIZE", "1024"))
        # 安全性のため、物理コア数(6)より少ないスレッド数(4)をデフォルトに設定します。
        self.n_threads = int(settings.get("LLAMACPP_THREADS", "4"))
        # Batch size controls peak memory during prompt evaluation.
        # Default reduced from 512 to 64 to prevent OOM on ~10GB Qwen3-30B model.
        self.n_batch = int(settings.get("LLAMACPP_BATCH_SIZE", "512"))
        self.n_gpu_layers = int(
            settings.get("LLAMACPP_GPU_LAYERS", "0")
        )  # CPU実行をデフォルトに
        self.use_mlock = str(settings.get("LLAMACPP_USE_MLOCK", "false")).lower() == "true"
        # mmap allows the model to be loaded from disk on demand, reducing initial RAM usage.
        self.use_mmap = str(settings.get("LLAMACPP_USE_MMAP", "true")).lower() == "true"
        self.max_tokens = int(settings.get("LLAMACPP_MAX_TOKENS", "2048"))
        self._is_busy = False
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

            # ウォームアップ推論: mmap ページキャッシュを温める
            logger.info("ウォームアップ推論を実行中...")
            llm_ref = self.llm
            await loop.run_in_executor(
                None,
                lambda: llm_ref.create_chat_completion(
                    messages=[{"role": "user", "content": "hi"}],
                    max_tokens=1,
                ),
            )
            logger.info("ウォームアップ完了")
        except Exception as e:
            logger.error(f"Llama-cpp モデルの初期化中にエラーが発生しました: {e}")
            if str(settings.get("DEV_MODE", "false")).lower() == "true":
                logger.warning("開発モードのため継続します（推論時にエラーになります）")
                return
            raise RuntimeError(f"Failed to load LLM: {e}")

    async def translate_with_llamacpp(
        self, original_word: str, paper_context: str, lang_name: str = "Japanese"
    ) -> str:
        """
        論文の文脈を考慮した翻訳を実行します。
        DICT_TRANSLATE_QWEN_PROMPT を直接使用し、DSPy を経由しません。
        """
        if self.llm is None:
            logger.error(
                "LLM が未初期化の状態で翻訳が要求されました。起動処理を確認してください。"
            )
            return "Error: LLM service is not initialized."

        # await のない箇所でフラグ確認・設定するため asyncio の協調スケジューリング上安全
        if self._is_busy:
            raise LlamaBusyError(
                f"Qwen is currently processing another request. word='{original_word[:30]}'"
            )
        self._is_busy = True

        from common.prompts import DICT_TRANSLATE_QWEN_PROMPT

        user_content = DICT_TRANSLATE_QWEN_PROMPT.format(
            paper_context=paper_context,
            target_word=original_word,
            lang_name=lang_name,
        )
        messages = [{"role": "user", "content": user_content}]

        try:
            import time

            logger.info(
                f"LLM 翻訳実行開始: word='{original_word[:50]}', lang='{lang_name}', context_len={len(paper_context)}"
            )
            start_time = time.time()
            loop = asyncio.get_running_loop()

            llm_ref = self.llm
            max_tokens = self.max_tokens

            def _run():
                raw = llm_ref.create_chat_completion(
                    messages=messages,
                    temperature=0.3,
                    max_tokens=max_tokens,
                )
                text = raw["choices"][0]["message"]["content"]
                # Qwen3 thinking ブロックを除去
                return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

            result = await loop.run_in_executor(None, _run)
            elapsed = time.time() - start_time
            logger.info(
                f"LLM 翻訳が正常に完了しました。経過時間: {elapsed:.2f}s, 結果文字数: {len(result)}"
            )
            return result

        except LlamaBusyError:
            raise
        except Exception as e:
            logger.error(f"LLM 推論エラー: {e}")
            return f"Translation error occurred: {str(e)}"
        finally:
            self._is_busy = False

    async def cleanup(self):
        """リソースを解放します。"""
        if self.llm:
            # llama-cpp-python 側に明示的な close はないが、参照を消しておく
            self.llm = None
            logger.info("Llama-cpp サービスをクリーンアップしました。")

"""
M2M100を使用した翻訳サービス
"""

import asyncio
import logging
import os

import ctranslate2
import sentencepiece as spm

from .utils import get_m2m100_lang_code

logger = logging.getLogger(__name__)


class M2M100TranslationService:
    """M2M100翻訳サービス"""

    def __init__(self):
        self.translator: ctranslate2.Translator | None = None
        self.tokenizer: spm.SentencePieceProcessor | None = None
        self.src_lang: str | None = "en"

        self.model_path = os.getenv("LOCAL_MODEL_PATH", "models/m2m100_ct2")

        # CTranslate2設定
        self.ct2_inter_threads = int(os.getenv("CT2_INTER_THREADS", "1"))
        self.ct2_intra_threads = int(os.getenv("CT2_INTRA_THREADS", "4"))

        # 翻訳パラメータ (単語翻訳用に最適化)
        self.beam_size = int(os.getenv("TRANSLATION_BEAM_SIZE", "2"))
        self.repetition_penalty = float(
            os.getenv("TRANSLATION_REPETITION_PENALTY", "1.1")
        )
        self.no_repeat_ngram_size = int(
            os.getenv("TRANSLATION_NO_REPEAT_NGRAM_SIZE", "1")
        )
        self.max_decoding_length = int(os.getenv("TRANSLATION_MAX_LENGTH", "32"))

    async def initialize(self):
        """モデルの初期化"""
        logger.info("M2M100翻訳モデルの初期化を開始...")

        # 開発環境でのスキップオプション
        if os.getenv("SKIP_MODEL_LOADING", "false").lower() == "true":
            logger.info("翻訳モデル読み込みをスキップしました（開発モード）")
            return

        # モデルファイルの存在確認
        if not os.path.exists(self.model_path):
            error_msg = f"モデルディレクトリが見つかりません: {self.model_path}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)

        # SentencePiece トークナイザーの読み込み
        tokenizer_path = os.path.join(self.model_path, "sentencepiece.bpe.model")
        if not os.path.exists(tokenizer_path):
            error_msg = f"トークナイザーが見つかりません: {tokenizer_path}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)

        try:
            self.tokenizer = spm.SentencePieceProcessor()
            self.tokenizer.load(tokenizer_path)

            # CTranslate2 翻訳モデルの読み込み
            self.translator = ctranslate2.Translator(
                self.model_path,
                device="cpu",
                inter_threads=self.ct2_inter_threads,
                intra_threads=self.ct2_intra_threads,
            )

            logger.info(f"M2M100翻訳モデルを読み込みました: {self.model_path}")

        except Exception as e:
            error_msg = f"M2M100翻訳モデルの読み込みに失敗しました: {e}"
            logger.error(error_msg)

            if os.getenv("DEV_MODE", "false").lower() == "true":
                logger.warning("開発モードのため、翻訳モデル読み込みエラーを無視します")
                return

            raise RuntimeError(error_msg) from e

    async def cleanup(self):
        """リソースのクリーンアップ"""
        if self.translator:
            self.translator = None
        if self.tokenizer:
            self.tokenizer = None
        logger.info("M2M100翻訳サービスをクリーンアップしました")

    def _prepare_input(self, text: str) -> list[str]:
        """入力テキストの準備"""
        pieces = self.tokenizer.encode_as_pieces(text)
        src_token = get_m2m100_lang_code(self.src_lang)
        return [src_token] + pieces + ["</s>"]

    async def translate(self, text: str, target_lang: str = "ja") -> dict:
        """単一テキストの翻訳実行と確信度の返却"""
        if not self.translator or not self.tokenizer:
            if os.getenv("DEV_MODE", "false").lower() == "true":
                return {"translation": f"[Dummy] {text}", "conf": 1.0}
            raise RuntimeError("M2M100モデル未初期化")

        input_tokens = self._prepare_input(text)
        tgt_code = get_m2m100_lang_code(target_lang)

        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            None,
            lambda: self.translator.translate_batch(
                [input_tokens],
                target_prefix=[[tgt_code]],
                beam_size=self.beam_size,
                repetition_penalty=self.repetition_penalty,
                no_repeat_ngram_size=self.no_repeat_ngram_size,
                max_decoding_length=self.max_decoding_length,
            ),
        )

        if results and results[0].hypotheses:
            result = results[0]
            output_tokens = result.hypotheses[0]
            score = result.scores[0] if result.scores else 0.0
            import math

            conf = math.exp(score)

            # Postprocess
            if output_tokens and output_tokens[0] == tgt_code:
                output_tokens = output_tokens[1:]
            translation = self.tokenizer.decode_pieces(output_tokens).strip()

            return {"translation": translation, "conf": conf, "model": "m2m100_ct2"}

        return {"translation": "", "conf": 0.0}

    async def translate_batch(
        self, texts: list[str], target_lang: str = "ja"
    ) -> list[dict]:
        """複数テキストの一括翻訳"""
        if not self.translator or not self.tokenizer:
            return [{"translation": "", "conf": 0.0}] * len(texts)

        tgt_code = get_m2m100_lang_code(target_lang)
        input_batches = [self._prepare_input(t) if t.strip() else [] for t in texts]

        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            None,
            lambda: self.translator.translate_batch(
                input_batches,
                target_prefix=[[tgt_code]] * len(input_batches),
                beam_size=self.beam_size,
                repetition_penalty=self.repetition_penalty,
                no_repeat_ngram_size=self.no_repeat_ngram_size,
                max_decoding_length=self.max_decoding_length,
            ),
        )

        outputs = []
        for i, result in enumerate(results):
            if input_batches[i] and result.hypotheses:
                output_tokens = result.hypotheses[0]
                score = result.scores[0] if result.scores else 0.0
                import math

                conf = math.exp(score)

                if output_tokens and output_tokens[0] == tgt_code:
                    output_tokens = output_tokens[1:]
                translation = self.tokenizer.decode_pieces(output_tokens).strip()
                outputs.append(
                    {"translation": translation, "conf": conf, "model": "m2m100_ct2"}
                )
            else:
                outputs.append({"translation": "", "conf": 0.0})

        return outputs

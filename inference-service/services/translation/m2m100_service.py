"""
M2M100を使用した翻訳サービス
"""

import asyncio
import logging
import math
import os

import ctranslate2
import sentencepiece as spm

from .utils import LANG_CODES, get_m2m100_lang_code

logger = logging.getLogger(__name__)


class M2M100TranslationService:
    """M2M100翻訳サービス"""

    def __init__(self):
        self.translator: ctranslate2.Translator | None = None
        self.tokenizer: spm.SentencePieceProcessor | None = None
        self.src_lang: str | None = "en"

        self.model_path = os.getenv("LOCAL_MODEL_PATH", "models/m2m100_ct2")
        self.lang_codes = LANG_CODES

        # CTranslate2設定
        self.ct2_inter_threads = int(os.getenv("CT2_INTER_THREADS", "1"))
        self.ct2_intra_threads = int(os.getenv("CT2_INTRA_THREADS", "4"))
        # int8 reduces working memory during inference without changing stored weights.
        self.ct2_compute_type = os.getenv("CT2_COMPUTE_TYPE", "int8")

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
                compute_type=self.ct2_compute_type,
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

    def _prepare_input(self, text: str, target_lang: str) -> list[str]:
        """入力テキストの準備

        M2M100では、入力テキストをそのままトークン化し、
        target_prefixでターゲット言語を指定する
        """

        # Tokenize using SentencePiece
        pieces = self.tokenizer.encode_as_pieces(text)
        src_token = get_m2m100_lang_code(self.src_lang)
        return [src_token] + pieces + ["</s>"]

    async def translate(self, text: str, target_lang: str = "ja") -> str:
        """単一テキストの翻訳"""
        if not self.translator or not self.tokenizer:
            if (
                os.getenv("DEV_MODE", "false").lower() == "true"
                or os.getenv("SKIP_MODEL_LOADING", "false").lower() == "true"
            ):
                logger.warning("開発モード: ダミー翻訳を返します")
                return f"[翻訳ダミー] {text} -> {target_lang}"
            raise RuntimeError(
                "翻訳モデルが初期化されていません。initialize()を先に呼び出してください。"
            )

        if not text.strip():
            return ""

        try:
            # Encode
            input_tokens = self._prepare_input(text, target_lang)

            # ターゲット言語コードを取得
            tgt_code = get_m2m100_lang_code(target_lang)

            # 翻訳実行（非同期実行のためスレッドプールを使用）
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                lambda: self.translator.translate_batch(
                    [input_tokens],
                    target_prefix=[[tgt_code]],  # List[Optional[List[str]]]形式
                    beam_size=self.beam_size,
                    repetition_penalty=self.repetition_penalty,
                    no_repeat_ngram_size=self.no_repeat_ngram_size,
                    max_decoding_length=self.max_decoding_length,
                    return_scores=True,
                ),
            )

            # Decode
            if results and results[0].hypotheses[0]:
                output_tokens = results[0].hypotheses[0]
                score = results[0].scores[0] if results[0].scores else 0.0
                conf = math.exp(score)
                translation = self._postprocess_output(output_tokens, tgt_code)
                logger.info(
                    f"翻訳結果: {text} -> {translation} (conf={conf:.3f}, model=M2M100)"
                )
                return {"translation": translation, "conf": conf, "model": "M2M100"}
            else:
                logger.warning("翻訳結果が空です")
                return {"translation": "", "conf": 0.0}

        except Exception as e:
            logger.error(f"翻訳エラー: {e}")
            # 開発モードではダミー翻訳を返す
            if os.getenv("DEV_MODE", "false").lower() == "true":
                logger.warning("開発モード: 翻訳エラーのためダミー翻訳を返します")
                return f"[翻訳エラー・ダミー] {text} -> {target_lang}"
            raise RuntimeError(f"翻訳処理に失敗しました: {e}") from e

    def _postprocess_output(self, tokens: list[str], target_lang: str) -> str:
        """出力の後処理"""
        # トークンをテキストに変換
        if tokens and tokens[0] == target_lang:
            tokens = tokens[1:]
        text = self.tokenizer.decode_pieces(tokens)

        return text.strip()

    async def translate_batch(
        self, texts: list[str], target_lang: str = "ja"
    ) -> list[str]:
        """複数テキストの一括翻訳"""
        if not self.translator or not self.tokenizer:
            # 開発モードではダミー翻訳を返す
            if (
                os.getenv("DEV_MODE", "false").lower() == "true"
                or os.getenv("SKIP_MODEL_LOADING", "false").lower() == "true"
            ):
                logger.warning("開発モード: ダミーバッチ翻訳を返します")
                return [f"[バッチ翻訳ダミー] {text} -> {target_lang}" for text in texts]
            raise RuntimeError(
                "翻訳モデルが初期化されていません。initialize()を先に呼び出してください。"
            )

        if not texts:
            return []

        try:
            # ターゲット言語コードを取得
            tgt_code = get_m2m100_lang_code(target_lang)

            # 入力準備
            input_batches = []
            for text in texts:
                if text.strip():
                    tokens = self._prepare_input(text, target_lang)
                    input_batches.append(tokens)
                else:
                    input_batches.append([])

            # バッチ翻訳実行
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                lambda: self.translator.translate_batch(
                    input_batches,
                    target_prefix=[[tgt_code]] * len(input_batches),
                    # beam_size=self.beam_size,
                    # repetition_penalty=self.repetition_penalty,
                    # no_repeat_ngram_size=self.no_repeat_ngram_size,
                    # max_decoding_length=self.max_decoding_length,
                    return_scores=True,
                ),
            )

            # 結果の後処理
            translations = []
            for i, result in enumerate(results):
                if input_batches[i] and result.hypotheses:
                    output_tokens = result.hypotheses[0]
                    score = result.scores[0] if result.scores else 0.0
                    conf = math.exp(score)
                    translation = self._postprocess_output(output_tokens, tgt_code)
                    translations.append(
                        {"translation": translation, "conf": conf, "model": "M2M100"}
                    )
                else:
                    translations.append({"translation": "", "conf": 0.0})

            return translations

        except Exception as e:
            logger.error(f"バッチ翻訳エラー: {e}")
            # 開発モードではダミー翻訳を返す
            if os.getenv("DEV_MODE", "false").lower() == "true":
                logger.warning("開発モード: バッチ翻訳エラーのためダミー翻訳を返します")
                return [
                    f"[バッチ翻訳エラー・ダミー] {text} -> {target_lang}"
                    for text in texts
                ]
            raise RuntimeError(f"バッチ翻訳処理に失敗しました: {e}") from e

    async def get_supported_languages(self) -> list[str]:
        """サポートされている言語コードのリストを取得"""
        return list(self.lang_codes.keys())

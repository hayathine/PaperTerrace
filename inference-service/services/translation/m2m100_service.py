"""
M2M100を使用した翻訳サービス
"""

import asyncio
import logging
import math
import os
import re

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

    def _prepare_input(self, text: str) -> list[str]:
        """入力テキストの準備"""
        pieces = self.tokenizer.encode_as_pieces(text)
        src_token = get_m2m100_lang_code(self.src_lang)
        return [src_token] + pieces + ["</s>"]

    def _prepare_input_word(self, word: str) -> list[str]:
        """単語翻訳用: ラッパー文にして文脈を与えたトークン列を構築する。

        単語単体より文脈文の方が M2M100 の翻訳精度が高い（特に専門用語のカタカナ転写）。
        出力は _extract_word_from_sentence() で日本語パターンマッチして抽出する。
        """
        src_token = get_m2m100_lang_code(self.src_lang)
        pieces = self.tokenizer.encode_as_pieces(f"The term {word} is used here.")
        return [src_token] + pieces + ["</s>"]

    @staticmethod
    def _is_single_word(text: str) -> bool:
        """テキストが単一単語かどうかを判定"""
        return len(text.strip().split()) == 1

    @staticmethod
    def _extract_word_from_sentence(sentence: str) -> str | None:
        """ラッパー文を翻訳した日本語出力から核となる単語部分を抽出する。

        M2M100 の典型的な出力パターン:
          - 「トランスフォーマー」という用語が… → 「」内を抽出
          - 注目という言葉はここで…            → という の直前を抽出
          - ここでグラディエントという…         → ここで〜という の間を抽出
        """
        # パターン1: 「term」 形式
        m = re.search(r"「(.+?)」", sentence)
        if m:
            return m.group(1).strip()

        # パターン2: ここで[は][、] term という 形式
        # 「ここでは、〜という」のように は や読点が続くケースを除外する
        m = re.search(r"ここでは?[、,]?\s*(.+?)(?:という|の)", sentence)
        if m:
            return m.group(1).strip()

        # パターン3: 文頭 term という 形式
        m = re.match(r"^(.+?)という", sentence)
        if m:
            candidate = m.group(1).strip()
            # 「その用語」「この用語」のような代名詞は除外
            if candidate not in ("その用語", "この用語", "その言葉", "この言葉"):
                return candidate

        return None

    async def translate(self, text: str, target_lang: str = "ja") -> dict:
        """単一テキストの翻訳実行と確信度の返却。

        単語単体では翻訳精度が低いため、単語の場合は文章に埋め込んで翻訳し、
        []内の翻訳結果だけを抽出して返す。
        """
        if not self.translator or not self.tokenizer:
            if os.getenv("DEV_MODE", "false").lower() == "true":
                return {"translation": f"[Dummy] {text}", "conf": 1.0}
            raise RuntimeError("M2M100モデル未初期化")

        is_word = self._is_single_word(text)
        input_tokens = (
            self._prepare_input_word(text) if is_word else self._prepare_input(text)
        )
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
                return_scores=True,
            ),
        )

        if results and results[0].hypotheses:
            result = results[0]
            output_tokens = result.hypotheses[0]
            score = result.scores[0] if result.scores else 0.0
            conf = math.exp(score)

            # Postprocess: strip leading language token
            if output_tokens and output_tokens[0] == tgt_code:
                output_tokens = output_tokens[1:]

            full_text = self.tokenizer.decode_pieces(output_tokens).strip()

            # 単語翻訳の場合: 日本語文パターンから核となる単語を抽出する。
            # 抽出できない場合は全文をそのまま返す。
            if is_word:
                extracted = self._extract_word_from_sentence(full_text)
                if extracted:
                    translation = extracted
                    logger.debug(f"単語抽出: {text!r} -> {translation!r} (全文: {full_text!r})")
                else:
                    translation = full_text
                    logger.debug(f"抽出失敗、全文返却: {text!r} -> {translation!r}")
            else:
                translation = full_text

            return {"translation": translation, "conf": conf, "model": "M2M100"}

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
                return_scores=True,
            ),
        )

        outputs = []
        for i, result in enumerate(results):
            if input_batches[i] and result.hypotheses:
                output_tokens = result.hypotheses[0]
                score = result.scores[0] if result.scores else 0.0
                conf = math.exp(score)

                if output_tokens and output_tokens[0] == tgt_code:
                    output_tokens = output_tokens[1:]
                translation = self.tokenizer.decode_pieces(output_tokens).strip()
                outputs.append(
                    {"translation": translation, "conf": conf, "model": "M2M100"}
                )
            else:
                outputs.append({"translation": "", "conf": 0.0})

        return outputs

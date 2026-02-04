"""
翻訳サービス
CTranslate2 を使用したM2M100推論
"""

import asyncio
import logging
import os
from typing import List, Optional
from pathlib import Path

try:
    import ctranslate2
    import sentencepiece as spm
except ImportError:
    ctranslate2 = None
    spm = None

logger = logging.getLogger(__name__)


class TranslationService:
    """翻訳サービス"""
    
    def __init__(self):
        self.translator: Optional[ctranslate2.Translator] = None
        self.tokenizer: Optional[spm.SentencePieceProcessor] = None
        
        self.model_path = os.getenv("LOCAL_MODEL_PATH", "models/m2m100_ct2")
        
        # CTranslate2設定
        self.ct2_inter_threads = int(os.getenv("CT2_INTER_THREADS", "1"))
        self.ct2_intra_threads = int(os.getenv("CT2_INTRA_THREADS", "4"))
        
        # 翻訳パラメータ
        self.beam_size = 4
        self.repetition_penalty = 1.2
        self.no_repeat_ngram_size = 3
        self.max_decoding_length = 256
        
        # 言語コードマッピング
        self.lang_codes = {
            "en": "__en__",
            "ja": "__ja__",
            "zh": "__zh__",
            "ko": "__ko__",
            "fr": "__fr__",
            "de": "__de__",
            "es": "__es__"
        }
    
    async def initialize(self):
        """モデルの初期化"""
        if ctranslate2 is None or spm is None:
            raise RuntimeError("CTranslate2 または SentencePiece がインストールされていません")
        
        model_dir = Path(self.model_path)
        if not model_dir.exists():
            raise FileNotFoundError(f"モデルディレクトリが見つかりません: {model_dir}")
        
        logger.info(f"翻訳モデルをロード中: {self.model_path}")
        
        try:
            # CTranslate2 Translator初期化
            self.translator = ctranslate2.Translator(
                str(model_dir),
                device="cpu",
                inter_threads=self.ct2_inter_threads,
                intra_threads=self.ct2_intra_threads,
                compute_type="int8"  # 量子化
            )
            
            # SentencePiece Tokenizer初期化
            tokenizer_path = model_dir / "sentencepiece.bpe.model"
            if not tokenizer_path.exists():
                raise FileNotFoundError(f"トークナイザーが見つかりません: {tokenizer_path}")
            
            self.tokenizer = spm.SentencePieceProcessor()
            self.tokenizer.load(str(tokenizer_path))
            
            logger.info("翻訳モデルのロード完了")
            
        except Exception as e:
            logger.error(f"翻訳モデルロードエラー: {e}")
            raise
    
    async def cleanup(self):
        """リソースのクリーンアップ"""
        if self.translator:
            self.translator = None
        if self.tokenizer:
            self.tokenizer = None
        logger.info("翻訳サービスをクリーンアップしました")
    
    def _prepare_input(self, text: str, source_lang: str, target_lang: str) -> List[str]:
        """入力テキストの準備"""
        # 言語コード変換
        src_code = self.lang_codes.get(source_lang, f"__{source_lang}__")
        tgt_code = self.lang_codes.get(target_lang, f"__{target_lang}__")
        
        # M2M100形式: [target_lang] source_text
        formatted_text = f"{tgt_code} {text}"
        
        # トークン化
        tokens = self.tokenizer.encode(formatted_text, out_type=str)
        
        return tokens
    
    def _postprocess_output(self, tokens: List[str]) -> str:
        """出力の後処理"""
        # トークンをテキストに変換
        text = self.tokenizer.decode(tokens)
        
        # 言語コードを除去
        for lang_code in self.lang_codes.values():
            text = text.replace(lang_code, "").strip()
        
        return text
    
    async def translate(self, text: str, source_lang: str = "en", target_lang: str = "ja") -> str:
        """単一テキストの翻訳"""
        if not self.translator or not self.tokenizer:
            raise RuntimeError("翻訳モデルが初期化されていません")
        
        if not text.strip():
            return ""
        
        try:
            # 入力準備
            input_tokens = self._prepare_input(text, source_lang, target_lang)
            
            # 翻訳実行（非同期実行のためスレッドプールを使用）
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                lambda: self.translator.translate_batch(
                    [input_tokens],
                    beam_size=self.beam_size,
                    repetition_penalty=self.repetition_penalty,
                    no_repeat_ngram_size=self.no_repeat_ngram_size,
                    max_decoding_length=self.max_decoding_length
                )
            )
            
            # 結果の後処理
            if results and results[0].hypotheses:
                output_tokens = results[0].hypotheses[0]
                translation = self._postprocess_output(output_tokens)
                return translation
            else:
                logger.warning("翻訳結果が空です")
                return ""
                
        except Exception as e:
            logger.error(f"翻訳エラー: {e}")
            raise
    
    async def translate_batch(self, texts: List[str], source_lang: str = "en", 
                            target_lang: str = "ja") -> List[str]:
        """複数テキストの一括翻訳"""
        if not self.translator or not self.tokenizer:
            raise RuntimeError("翻訳モデルが初期化されていません")
        
        if not texts:
            return []
        
        try:
            # 入力準備
            input_batches = []
            for text in texts:
                if text.strip():
                    tokens = self._prepare_input(text, source_lang, target_lang)
                    input_batches.append(tokens)
                else:
                    input_batches.append([])
            
            # バッチ翻訳実行
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                lambda: self.translator.translate_batch(
                    input_batches,
                    beam_size=self.beam_size,
                    repetition_penalty=self.repetition_penalty,
                    no_repeat_ngram_size=self.no_repeat_ngram_size,
                    max_decoding_length=self.max_decoding_length
                )
            )
            
            # 結果の後処理
            translations = []
            for i, result in enumerate(results):
                if input_batches[i] and result.hypotheses:
                    output_tokens = result.hypotheses[0]
                    translation = self._postprocess_output(output_tokens)
                    translations.append(translation)
                else:
                    translations.append("")
            
            return translations
            
        except Exception as e:
            logger.error(f"バッチ翻訳エラー: {e}")
            raise
    
    async def get_supported_languages(self) -> List[str]:
        """サポートされている言語コードのリストを取得"""
        return list(self.lang_codes.keys())
import asyncio
import os
from typing import Optional

import ctranslate2
import sentencepiece as spm

from src.core.logger import logger


class LocalTranslatorService:
    """
    Local machine translation service using M2M100 converted to CTranslate2 format.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(LocalTranslatorService, cls).__new__(cls)
            cls._instance._initialized_service = False
        return cls._instance

    def __init__(self, model_path: str = "models/m2m100_ct2"):
        # Prevent multiple initializations if already initialized
        if hasattr(self, "_initialized_service") and self._initialized_service:
            return

        self.model_path = model_path
        self.translator = None
        self.sp_processor = None
        self._initialized = False
        self._initialized_service = True

        self._unload_timer_task = None
        self._unload_delay = 600  # 10 minutes for translator
        self._load_lock = asyncio.Lock()

    async def _ensure_loaded(self):
        """モデルがロードされていることを保証する（非同期版）"""
        from src.core.utils.memory import register_model_activity

        register_model_activity(self, self._unload_delay)
        async with self._load_lock:
            if not self._initialized:
                self._load_model()

    def _load_model(self):
        try:
            if not os.path.exists(self.model_path):
                logger.warning(
                    f"[LocalTranslator] Model directory not found at {self.model_path}. "
                    "Skipping local translator initialization."
                )
                return

            # Load CTranslate2 translator
            # Use 'cpu' by default as this is a background/secondary service
            self.translator = ctranslate2.Translator(self.model_path, device="cpu")

            # Load SentencePiece processor
            sp_path = os.path.join(self.model_path, "sentencepiece.bpe.model")
            if os.path.exists(sp_path):
                self.sp_processor = spm.SentencePieceProcessor()
                self.sp_processor.load(sp_path)
                logger.info(f"[LocalTranslator] M2M100 loaded successfully from {self.model_path}")
                self._initialized = True
            else:
                logger.error(f"[LocalTranslator] SentencePiece model not found at {sp_path}")
        except Exception as e:
            logger.error(f"[LocalTranslator] Failed to load local translator: {e}")

    def unload(self):
        """メモリを解放するためにモデルをアンロードする"""
        if self._initialized:
            logger.info("[LocalTranslator] Unloading M2M100 model...")
            del self.translator
            del self.sp_processor
            self.translator = None
            self.sp_processor = None
            self._initialized = False

            from src.core.utils.memory import cleanup_memory

            cleanup_memory()
            logger.info("[LocalTranslator] Model unloaded.")

    def is_available(self) -> bool:
        return self._initialized or os.path.exists(self.model_path)

    async def translate(
        self, text: str, src_lang: str = "en", tgt_lang: str = "ja"
    ) -> Optional[str]:
        """
        Translate text using M2M100.
        Default: English -> Japanese
        """
        await self._ensure_loaded()
        if not self._initialized or not text.strip():
            return None

        try:
            # Language prefixes for M2M100
            # codes are usually __en__, __ja__, etc.
            src_prefix = f"__{src_lang}__"
            tgt_prefix = f"__{tgt_lang}__"

            # Tokenize
            tokens = self.sp_processor.encode(text, out_type=str)
            if not tokens:
                return None

            tokens = [src_prefix] + tokens

            # Translate
            results = self.translator.translate_batch(
                [tokens],
                target_prefix=[[tgt_prefix]],
                max_batch_size=1,
                beam_size=5,
                repetition_penalty=1.5,
                no_repeat_ngram_size=2,
                max_decoding_length=64,  # Dictionary lemmas are short
            )

            if not results or not results[0].hypotheses:
                logger.warning("[LocalTranslator] No hypotheses returned")
                return None

            output_tokens = results[0].hypotheses[0]

            # Remove prefix from output tokens
            if output_tokens and output_tokens[0] == tgt_prefix:
                output_tokens = output_tokens[1:]

            # Decode
            result = self.sp_processor.decode(output_tokens)
            return result
        except Exception as e:
            logger.error(f"[LocalTranslator] Translation failed for '{text[:50]}...': {e}")
            return None

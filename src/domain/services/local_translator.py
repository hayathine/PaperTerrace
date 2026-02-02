import os

import ctranslate2
import sentencepiece as spm

from src.logger import logger


class LocalTranslator:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LocalTranslator, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.model_path = os.getenv("LOCAL_MODEL_PATH", "models/m2m100_ct2")

        self.translator: ctranslate2.Translator | None = None  # type: ignore[name-defined]
        self.sp_model: spm.SentencePieceProcessor | None = None

        if not os.path.exists(self.model_path):
            logger.warning(
                f"Local translation model not found at {self.model_path}. Local translation will be unavailable."
            )
        else:
            try:
                # Load CTranslate2 translator
                self.translator = ctranslate2.Translator(  # type: ignore[attr-defined]
                    self.model_path,
                    device="cpu",
                    compute_type="int8",
                    inter_threads=1,
                    intra_threads=2,
                )

                # Load SentencePiece model for tokenization
                spm_path = os.path.join(self.model_path, "sentencepiece.bpe.model")
                if os.path.exists(spm_path):
                    self.sp_model = spm.SentencePieceProcessor(model_file=spm_path)  # type: ignore[call-arg]
                    logger.info(f"Loaded SentencePiece model from {spm_path}")
                else:
                    logger.error(f"SentencePiece model not found at {spm_path}")
                    return

                self._initialized = True
                logger.info("LocalTranslator (M2M100) initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize LocalTranslator: {e}")

    async def prewarm(self):
        """Pre-initialize models to avoid delay on first request."""
        if not self._initialized:
            logger.info("Pre-warming LocalTranslator (M2M100)...")
            # Running in executor to not block the event loop
            import asyncio
            from concurrent.futures import ThreadPoolExecutor

            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor(max_workers=1) as pool:
                await loop.run_in_executor(pool, self.__init__)

    def translate(self, text: str, src_lang: str = "en", tgt_lang: str = "ja") -> str | None:
        if not self._initialized or self.translator is None or self.sp_model is None:
            return None

        try:
            # Get language tokens
            src_token = f"__{src_lang}__"
            tgt_token = f"__{tgt_lang}__"

            # Tokenize using SentencePiece
            pieces = self.sp_model.encode_as_pieces(text)  # type: ignore[attr-defined]
            source_tokens = [src_token] + pieces + ["</s>"]

            # Translate
            results = self.translator.translate_batch([source_tokens], target_prefix=[[tgt_token]])
            target_tokens = results[0].hypotheses[0]

            # Remove target language token if present
            if target_tokens and target_tokens[0] == tgt_token:
                target_tokens = target_tokens[1:]

            # Detokenize using SentencePiece
            translation = self.sp_model.decode_pieces(target_tokens)  # type: ignore[attr-defined]
            return translation.strip()

        except Exception as e:
            logger.error(f"Local translation error for '{text}': {e}", extra={"error": str(e)})
            return None


def get_local_translator():
    return LocalTranslator()

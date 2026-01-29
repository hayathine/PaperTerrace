import os

import ctranslate2
import transformers

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
        self.tokenizer_path = "facebook/m2m100_418M"

        self.translator: ctranslate2.Translator | None = None
        self.tokenizer: transformers.PreTrainedTokenizerBase | None = None

        if not os.path.exists(self.model_path):
            logger.warning(
                f"Local translation model not found at {self.model_path}. Local translation will be unavailable."
            )
        else:
            try:
                # Load CTranslate2 translator
                self.translator = ctranslate2.Translator(
                    self.model_path,
                    device="cpu",
                    compute_type="int8",
                    inter_threads=1,
                    intra_threads=2,
                )

                # Load tokenizer
                self.tokenizer = transformers.AutoTokenizer.from_pretrained(self.tokenizer_path)
                self._initialized = True
                logger.info("LocalTranslator (M2M100) initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize LocalTranslator: {e}")

    def translate(self, text: str, src_lang: str = "en", tgt_lang: str = "ja") -> str | None:
        if not self._initialized or self.translator is None or self.tokenizer is None:
            return None

        try:
            # Type hinting helpers for static analysis
            translator = self.translator
            tokenizer = self.tokenizer

            # Prepare source tokens
            # M2M100 needs special language tokens
            setattr(tokenizer, "src_lang", src_lang)
            source = tokenizer.convert_ids_to_tokens(tokenizer.encode(text))

            # Target language token
            lang_code_to_token = getattr(tokenizer, "lang_code_to_token", {})
            target_prefix = [lang_code_to_token[tgt_lang]]

            # Translate
            results = translator.translate_batch([source], target_prefix=[target_prefix])
            target_tokens = results[0].hypotheses[0]

            # Decode
            # Remove target prefix token if present
            if target_tokens and target_tokens[0] == target_prefix[0]:
                target_tokens = target_tokens[1:]

            translation = tokenizer.decode(tokenizer.convert_tokens_to_ids(target_tokens))
            if isinstance(translation, str):
                return translation.strip().strip("'\"")
            return None
        except Exception as e:
            logger.error(f"Local translation error for '{text}': {e}")
            return None


def get_local_translator():
    return LocalTranslator()

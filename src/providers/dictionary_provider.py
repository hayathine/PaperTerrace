from jamdict import Jamdict

from src.logger import logger


class DictionaryProvider:
    def __init__(self):
        # Jamdictインスタンスの生成（内部で初期化が行われます）
        self.jam = Jamdict()
        self._initialized = True
        logger.info("Jamdict initialized")

    def ensure_initialized(self):
        """
        Jamdictは内部のSQLiteを自動的に使用します。
        """
        pass

    def lookup(self, word: str) -> str | None:
        """
        ワードを検索して日本語の定義を返します。
        """
        if not word:
            return None

        try:
            # 検索実行
            result = self.jam.lookup(word)

            # 結果から最初の意味（日本語）を抽出
            if result.entries:
                # 最初の項目の、最初の意味の文字列を返す
                definitions = []
                for sense in result.entries[0].senses:
                    # 日本語の定義を探す
                    glosses = [g.gloss for g in sense.gloss]
                    definitions.append(", ".join(glosses))

                if definitions:
                    return " / ".join(definitions)

            return None
        except Exception as e:
            logger.error(f"Jamdict lookup error for '{word}': {e}")
            return None


# シングルトン化して再利用（高速化の鍵）
_instance = None


def get_dictionary_provider():
    global _instance
    if _instance is None:
        _instance = DictionaryProvider()
    return _instance


if __name__ == "__main__":
    # テスト
    provider = get_dictionary_provider()
    result = provider.lookup("apple")
    print(f"Lookup 'apple': {result}")

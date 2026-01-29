import os

from src.logger import logger


class DictionaryProvider:
    def __init__(self):
        self.use_jamdict = os.getenv("USE_JAMDICT", "false").lower() == "true"
        self.jam = None

        if self.use_jamdict:
            try:
                from jamdict import Jamdict

                # Jamdictインスタンスの生成（内部で初期化が行われます）
                self.jam = Jamdict()
                logger.info("Jamdict initialized and enabled")
            except Exception as e:
                logger.error(f"Failed to initialize Jamdict: {e}")
                self.use_jamdict = False
        else:
            logger.info("Jamdict is disabled by configuration (USE_JAMDICT=false)")

    def ensure_initialized(self):
        """
        Jamdictは内部のSQLiteを自動的に使用します。
        """
        pass

    def lookup(self, word: str) -> str | None:
        """
        ワードを検索して日本語の定義を返します。
        """
        if not self.use_jamdict or self.jam is None:
            return None

        if not word:
            return None

        try:
            # 検索実行
            result = self.jam.lookup(word)
            logger.debug(f"Jamdict lookup result for '{word}': {result.entries[:5]}")

            if result.entries:
                meanings = []
                for entry in result.entries:
                    # Jamdict (JMdict) の正しい属性名は kanji_forms と kana_forms です
                    # 各フォームの文字列表記は .text で取得できます
                    kanji_list = getattr(entry, "kanji_forms", [])
                    kana_list = getattr(entry, "kana_forms", [])

                    kanji = [getattr(k, "text", "") for k in kanji_list if hasattr(k, "text")]
                    kana = [getattr(k, "text", "") for k in kana_list if hasattr(k, "text")]

                    if kanji:
                        # 漢字がある場合は「漢字 (かな)」の形式にする
                        meanings.append(f"{kanji[0]} ({kana[0]})" if kana else kanji[0])
                    elif kana:
                        # かなのみの場合
                        meanings.append(kana[0])

                if meanings:
                    # 重複を除いて上位数件を結合
                    return ", ".join(list(dict.fromkeys(meanings))[:3])

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

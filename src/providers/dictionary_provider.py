class DictionaryProvider:
    def __init__(self):
        pass


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

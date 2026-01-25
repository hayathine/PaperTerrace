import re

from fugashi import Tagger
from pydantic import BaseModel, Field

tagger = Tagger("-Owakati")


class KanjiCheckResult(BaseModel):
    word: str = Field(..., description="The word being checked")
    is_difficult: bool = Field(
        ..., description="Whether the word is considered difficult"
    )


def is_kanji(text):
    # 漢字が含まれているか判定する正規表現
    return re.search(r"[一-龠々]", text) is not None


def extract_kanji_words(text):
    # lemma が "*" の場合は surface を使う
    words = []
    for w in tagger(text):
        if is_kanji(w.surface):
            # lemma（辞書形）を優先し、無ければ surface を使う
            lemma = w.feature.lemma if w.feature.lemma != "*" else w.surface
            words.append(lemma)
    unique_words = list(set(words))
    return unique_words

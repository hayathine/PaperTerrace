from concurrent.futures import ThreadPoolExecutor

import spacy
from dotenv import load_dotenv
from jamdict import Jamdict

load_dotenv()

"""
英語の文章を処理するための設定とリソースの初期化"""

# spaCyの英語モデルをロード
nlp = spacy.load(
    "en_core_web_sm",
    disable=[
        "ner",
        "parser",
        "tok2vec",
    ],
)
jam = Jamdict()
executor = ThreadPoolExecutor(max_workers=4)

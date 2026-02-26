from typing import Any, Dict, List


def sort_blocks(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    ブロックをリーディングオーダーでソートする（Y座標メイン、次にX座標）
    ※ 2段組み対応のためのヒューリスティック
    """
    # X座標で大まかに列を分ける (例: 画像の半分のX座標より右か左かなど)
    # ここではシンプルに、まず左半分の要素を上から下へ、次に右半分の要素を上から下へ並べる簡易的な2段組対応

    # ページの幅の概算(すべてのブロックのx_maxの最大値)
    if not blocks:
        return []

    max_x = max(b["bbox"][2] for b in blocks)
    mid_x = max_x / 2.0

    left_col = []
    right_col = []
    span_col = []  # ページ全体をまたぐようなブロック

    for b in blocks:
        bbox = b["bbox"]
        # Handle both list [x1, y1, x2, y2] and dict {"x_min": x1, ...} formats
        if isinstance(bbox, dict):
            bx1 = bbox.get("x_min") or bbox.get("x0") or bbox.get("left")
            bx2 = bbox.get("x_max") or bbox.get("x1") or bbox.get("right")
            by1 = bbox.get("y_min") or bbox.get("top") or bbox.get("y0")
        else:
            bx1, by1, bx2, _ = bbox

        width = bx2 - bx1
        if width > max_x * 0.7:  # 70%以上の幅があれば1段ぶち抜きと判断
            span_col.append(b)
        elif (bx1 + bx2) / 2 < mid_x:
            left_col.append(b)
        else:
            right_col.append(b)

    # それぞれを Y座標 でソート
    def sort_by_y(col):
        def get_y(item):
            bbox = item["bbox"]
            if isinstance(bbox, dict):
                return bbox.get("y_min") or bbox.get("top") or bbox.get("y0")
            return bbox[1]

        return sorted(col, key=get_y)

    left_col = sort_by_y(left_col)
    right_col = sort_by_y(right_col)
    span_col = sort_by_y(span_col)

    # 簡単のため上から合流
    # 実際は span_col のY座標に応じて left_col/right_col の間に入るべきだが、今回はシンプルに
    # left_col -> right_col の順をベースに、Yでマージ

    # 実際にはより高度な XY-cut アルゴリズムなどが使われる
    # ここではY座標の許容誤差を用いたシンプルなソートを行う（2段組を正しく読むため）

    return left_col + right_col + span_col


def generate_markdown_from_layout(
    words: List[Dict[str, Any]], layout_blocks: List[Dict[str, Any]]
) -> str:
    """
    PP-DocLayoutなどの解析結果ブロックと、pdfplumber等で抽出した全単語情報から、
    Markdown形式のテキストを生成する。

    layout_blocks format:
    [
      {"class_id": 0, "class_name": "Text", "bbox": [x1, y1, x2, y2], "score": 0.9},
      ...
    ]
    words format:
    [
      {"word": "Hello", "bbox": [x1, y1, x2, y2]},
      ...
    ]
    """
    # 1. ブロックをリーディングオーダーにソート
    sorted_blocks = sort_blocks(layout_blocks)

    if not sorted_blocks:
        # Layout detection unavailable or empty, fallback to plain text reconstruction
        y_tolerance = 5
        words_sorted = sorted(
            words, key=lambda w: (round(w["bbox"][1] / y_tolerance), w["bbox"][0])
        )
        return " ".join([w["word"] for w in words_sorted])

    # 2. 各ブロックに単語を割り当てる
    for b in sorted_blocks:
        b["words"] = []

    # 単語の中心点がどのブロックに含まれるかを判定
    for w in words:
        wx_center = (w["bbox"][0] + w["bbox"][2]) / 2
        wy_center = (w["bbox"][1] + w["bbox"][3]) / 2

        assigned = False
        for b in sorted_blocks:
            bbox = b["bbox"]
            if isinstance(bbox, dict):
                bx1 = bbox.get("x_min") or bbox.get("x0") or bbox.get("left")
                bx2 = bbox.get("x_max") or bbox.get("x1") or bbox.get("right")
                by1 = bbox.get("y_min") or bbox.get("top") or bbox.get("y0")
                by2 = bbox.get("y_max") or bbox.get("bottom") or bbox.get("y1")
            else:
                bx1, by1, bx2, by2 = bbox

            margin = 5  # ブロックの境界の少し外側も許容
            if (bx1 - margin) <= wx_center <= (bx2 + margin) and (
                by1 - margin
            ) <= wy_center <= (by2 + margin):
                b["words"].append(w)
                assigned = True
                break

        # もしどのブロックにも属さなければ、未分類として処理（必要なら）
        if not assigned:
            pass  # ここでは無視するか、あるいは別途テキストとして扱う

    # 3. ボックス内の単語をY->Xの順でソート（同じ行としてYの誤差をある程度許容）
    for b in sorted_blocks:
        # 行ごとにまとめるため、Y座標の閾値を設定
        y_tolerance = 5
        b["words"] = sorted(
            b["words"], key=lambda w: (round(w["bbox"][1] / y_tolerance), w["bbox"][0])
        )
        b["text"] = " ".join([w["word"] for w in b["words"]])

    # 4. Markdown文字列に組み立て
    md_lines = []

    for b in sorted_blocks:
        text = b.get("text", "").strip()
        if not text:
            # textがない場合（Figure単体で文字がないなど）
            if b.get("class_name") == "Figure":
                md_lines.append(f"\n![Figure]({b['bbox']})\n")
            elif b.get("class_name") == "Table":
                md_lines.append("\n[Table Area]\n")
            continue

        c_name = b.get("class_name", "Text").lower()

        if c_name == "title":
            md_lines.append(f"\n# {text}\n")
        elif "figure" in c_name:
            if "caption" in c_name:
                md_lines.append(f"\n*Figure Caption*: {text}\n")
            else:
                md_lines.append(
                    f"\n![Figure]({b['bbox']})\n"
                )  # もし文字が内部にあれば出力？
        elif "table" in c_name:
            if "caption" in c_name:
                md_lines.append(f"\n*Table Caption*: {text}\n")
            else:
                md_lines.append(f"\n[Table Data: {text}]\n")
        elif "equation" in c_name or "formula" in c_name:
            md_lines.append(f"\n\n$$ {text} $$\n\n")
        elif c_name == "list":
            md_lines.append(f"- {text}")
        elif c_name in ["header", "footer"]:
            # ヘッダーやフッターは無視するか注釈にする
            pass
        else:
            # 通常のテキスト
            md_lines.append(f"{text}\n")

    return "\n".join(md_lines).strip()

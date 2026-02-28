import json

# import dspy # Placeholder for DSPy batch optimization pipeline


def export_contrastive_data(db_conn, since: str, output_path: str):
    """
    Cloud SQLから対照学習データをエクスポート
    オフライン学習用にJSONLファイルに保存
    """
    # Requires DB Connection object or session depending on SQLAlchemy usage
    rows = db_conn.execute(
        """
        SELECT * FROM contrastive_learning_records
        WHERE created_at >= %s
        ORDER BY created_at DESC
    """,
        (since,),
    ).fetchall()

    with open(output_path, "w") as f:
        for row in rows:
            record = dict(row)
            # ベクトル化テキストを付加
            # record["user_text"] = build_user_text_from_dict(record)
            # record["paper_text"] = build_paper_text_from_dict(record)
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"対照学習データ: {len(rows)}件をエクスポート")

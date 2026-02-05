#!/bin/bash
# PaddleX モデルのクリーンアップスクリプト
# 不要なモデルを削除して、必要なモデルのみを保持

PADDLE_DIR="$HOME/.paddlex/official_models"

echo "=== PaddleX Model Cleanup ==="
echo "Current size:"
du -sh "$PADDLE_DIR"
echo ""

# 保持するモデル（レイアウト解析用）
KEEP_MODELS=(
    "PP-DocLayout_plus-L"  # レイアウト検出
)

# 削除対象のモデル
DELETE_MODELS=(
    "PP-Chart2Table"
    "PP-DocBlockLayout"
    "PP-FormulaNet_plus-L"
    "PP-LCNet_x1_0_doc_ori"
    "PP-LCNet_x1_0_table_cls"
    "PP-LCNet_x1_0_textline_ori"
    "PP-OCRv5_server_det"
    "PP-OCRv5_server_rec"
    "RT-DETR-L_wired_table_cell_det"
    "RT-DETR-L_wireless_table_cell_det"
    "SLANeXt_wired"
    "SLANet_plus"
    "UVDoc"
    "en_PP-OCRv5_mobile_rec"
)

echo "Models to delete:"
for model in "${DELETE_MODELS[@]}"; do
    if [ -d "$PADDLE_DIR/$model" ]; then
        size=$(du -sh "$PADDLE_DIR/$model" | cut -f1)
        echo "  - $model ($size)"
        rm -rf "$PADDLE_DIR/$model"
    fi
done

echo ""
echo "Models to keep:"
for model in "${KEEP_MODELS[@]}"; do
    if [ -d "$PADDLE_DIR/$model" ]; then
        size=$(du -sh "$PADDLE_DIR/$model" | cut -f1)
        echo "  - $model ($size)"
    fi
done

echo ""
echo "After cleanup:"
du -sh "$PADDLE_DIR"

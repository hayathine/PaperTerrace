"""
PP-DocLayout-L INT8 PTQ 量子化スクリプト

使い方:
    # PDF ディレクトリを直接指定（推奨）
    uv run --group quantize python quantize_layout_model.py \
        --pdfs ../backend/src/static/pdfs

    # キャリブレーション画像ディレクトリを指定
    uv run --group quantize python quantize_layout_model.py --images /path/to/images

    # 画像なしで合成データを使う（精度は落ちる）
    uv run --group quantize python quantize_layout_model.py --synthetic

オプション:
    --model     入力モデル XML パス (default: models/paddl2vino/PP-DocLayout-L_infer.xml)
    --output    出力モデル XML パス (default: models/paddl2vino/PP-DocLayout-L_int8.xml)
    --pdfs      PDF ディレクトリ（各 PDF から複数ページを抽出）
    --images    キャリブレーション画像ディレクトリ (PNG/JPG)
    --synthetic 合成データでキャリブレーション（画像なし時のフォールバック）
    --count     キャリブレーションサンプル数 (default: 300)
    --dpi       PDF レンダリング DPI (default: 150)
    --max-pages PDF 1 ファイルあたりの最大ページ数 (default: 20)
"""

import argparse
import sys
import logging
from pathlib import Path

import cv2
import numpy as np
import openvino as ov
import nncf
from nncf.common.logging import nncf_logger

nncf_logger.setLevel(logging.WARNING)

# ────────────────────────────────────────────────
# 前処理（openvino_layout_service と同一パイプライン）
# ────────────────────────────────────────────────

def preprocess_image(img: np.ndarray) -> dict[str, np.ndarray]:
    """画像を前処理してモデル入力形式に変換する。

    推論コード（openvino_layout_service.py）と完全に同一の前処理を行う:
    - im_shape   : letterbox後は常に (640, 640) → モデル入力サイズ固定
    - scale_factor: モデルへの入力は常に [[1.0, 1.0]] （後処理で実スケールを使う設計）
    """
    target_h, target_w = 640, 640
    h, w = img.shape[:2]
    scale = min(target_h / h, target_w / w)
    new_h, new_w = int(h * scale), int(w * scale)

    # BGR → RGB（PIL.Image.open と同様）
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    resized = cv2.resize(img_rgb, (new_w, new_h))
    canvas = np.zeros((target_h, target_w, 3), dtype=np.uint8)
    pad_h = (target_h - new_h) // 2
    pad_w = (target_w - new_w) // 2
    canvas[pad_h : pad_h + new_h, pad_w : pad_w + new_w] = resized

    # 推論コードと同じ固定値（_preprocess_from_bytes / _preprocess 参照）
    im_shape = np.array([[640.0, 640.0]], dtype=np.float32)
    scale_factor = np.array([[1.0, 1.0]], dtype=np.float32)

    # [0,1] スケールのみ（mean/std 正規化なし: norm_type="none"）
    image = canvas.astype(np.float32) / 255.0
    image = image.transpose(2, 0, 1)[np.newaxis]  # HWC → NCHW

    return {
        "image": image,
        "im_shape": im_shape,
        "scale_factor": scale_factor,
    }


# ────────────────────────────────────────────────
# データセット生成
# ────────────────────────────────────────────────

def pdf_dataset(pdf_dir: Path, count: int, dpi: int, max_pages: int):
    """PDF ファイルからページ画像を生成してキャリブレーションデータを返す。"""
    try:
        from pdf2image import convert_from_path
    except ImportError:
        print("エラー: pdf2image が必要です。uv add --group quantize pdf2image")
        sys.exit(1)

    pdf_paths = sorted(pdf_dir.glob("*.pdf"))
    if not pdf_paths:
        print(f"エラー: {pdf_dir} に PDF ファイルが見つかりません。")
        sys.exit(1)

    print(f"  {len(pdf_paths)} 件の PDF を検出")

    yielded = 0
    cycle = 0

    while yielded < count:
        for pdf_path in pdf_paths:
            if yielded >= count:
                break
            try:
                pages = convert_from_path(
                    str(pdf_path),
                    dpi=dpi,
                    first_page=1,
                    last_page=max_pages,
                )
            except Exception as e:
                print(f"  スキップ ({pdf_path.name}): {e}")
                continue

            for page_img in pages:
                if yielded >= count:
                    break
                # PIL → BGR numpy
                img = cv2.cvtColor(np.array(page_img), cv2.COLOR_RGB2BGR)
                yield preprocess_image(img)
                yielded += 1
                if yielded % 50 == 0:
                    print(f"  {yielded}/{count} サンプル完了...")

        cycle += 1
        if cycle > 10:
            # PDF が少なすぎる場合の無限ループ防止
            print(f"  警告: {yielded} サンプルで打ち切り（PDF 不足）")
            break


def image_dataset(image_dir: Path, count: int):
    """画像ディレクトリからキャリブレーションデータセットを生成する。"""
    extensions = {".png", ".jpg", ".jpeg", ".bmp", ".tiff"}
    paths = [p for p in sorted(image_dir.iterdir()) if p.suffix.lower() in extensions]

    if not paths:
        print(f"エラー: {image_dir} に画像ファイルが見つかりません。")
        sys.exit(1)

    print(f"  {len(paths)} 枚の画像を検出 → {count} サンプル使用")

    loaded = 0
    idx = 0
    while loaded < count:
        path = paths[idx % len(paths)]
        idx += 1
        img = cv2.imread(str(path))
        if img is None:
            print(f"  スキップ（読み込み失敗）: {path.name}")
            continue
        yield preprocess_image(img)
        loaded += 1


def synthetic_dataset(count: int):
    """合成画像（論文ページ風ノイズ）でキャリブレーションデータセットを生成する。"""
    print(f"  合成データ {count} サンプルを生成します")
    rng = np.random.default_rng(42)
    for _ in range(count):
        img = np.full((1000, 800, 3), 240, dtype=np.uint8)
        for _ in range(rng.integers(5, 20)):
            x1, y1 = rng.integers(0, 700), rng.integers(0, 900)
            x2, y2 = x1 + rng.integers(50, 200), y1 + rng.integers(10, 40)
            color = int(rng.integers(0, 80))
            cv2.rectangle(img, (x1, y1), (x2, y2), (color, color, color), -1)
        yield preprocess_image(img)


# ────────────────────────────────────────────────
# メイン
# ────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="PP-DocLayout-L INT8 PTQ 量子化")
    parser.add_argument(
        "--model",
        default="models/paddl2vino/PP-DocLayout-L_infer.xml",
        help="入力モデル XML パス",
    )
    parser.add_argument(
        "--output",
        default="models/paddle2vino/PP-DocLayout-L_int8.xml",
        help="出力モデル XML パス",
    )
    parser.add_argument(
        "--pdfs",
        type=Path,
        default=None,
        help="PDF ディレクトリ（各 PDF からページ画像を抽出）",
    )
    parser.add_argument(
        "--images",
        type=Path,
        default=None,
        help="キャリブレーション画像ディレクトリ",
    )
    parser.add_argument(
        "--synthetic",
        action="store_true",
        help="合成データでキャリブレーション",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=300,
        help="キャリブレーションサンプル数",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=150,
        help="PDF レンダリング DPI（高いほど高品質、遅い）",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=20,
        help="PDF 1 ファイルあたりの最大ページ数",
    )
    args = parser.parse_args()

    # 引数チェック
    sources = [args.pdfs, args.images, args.synthetic]
    if not any(sources):
        parser.error("--pdfs / --images / --synthetic のいずれかを指定してください。")
    if args.pdfs and not args.pdfs.is_dir():
        parser.error(f"ディレクトリが見つかりません: {args.pdfs}")
    if args.images and not args.images.is_dir():
        parser.error(f"ディレクトリが見つかりません: {args.images}")

    model_path = Path(args.model)
    output_path = Path(args.output)

    if not model_path.exists():
        print(f"エラー: モデルが見つかりません: {model_path}")
        sys.exit(1)

    print(f"モデル読み込み: {model_path}")
    core = ov.Core()
    model = core.read_model(str(model_path))

    # キャリブレーションデータセット
    print(f"\nキャリブレーションデータ準備 ({args.count} サンプル):")
    if args.pdfs:
        dataset_gen = pdf_dataset(args.pdfs, args.count, args.dpi, args.max_pages)
    elif args.images:
        dataset_gen = image_dataset(args.images, args.count)
    else:
        dataset_gen = synthetic_dataset(args.count)

    calibration_dataset = nncf.Dataset(dataset_gen)

    # INT8 PTQ 量子化
    # 座標計算・確率計算に関わる演算タイプを一括除外する（NNCF 3.0対応）
    # Convolution / MatMul はINT8化して高速化の恩恵を得る
    detection_head_scope = nncf.IgnoredScope(
        names=[
            "im_shape",
            "scale_factor",
        ],
        types=[
            "Multiply",    # スケール引き伸ばし
            "Divide",      # 正規化
            "Add",         # オフセット加算
            "Subtract",    # 差分計算
            "Exp",         # Bbox指数関数回帰
            "Softmax",     # クラス確率・DFL
            "ReduceSum",   # Bboxデコード積分計算
            "GridSample",  # 特徴マップリサンプリング
        ],
        validate=False,    # モデルに存在しない型はスキップ（エラーにしない）
    )

    print("\nINT8 PTQ 量子化を実行中（座標計算系の演算を保護）...")
    quantized_model = nncf.quantize(
        model,
        calibration_dataset,
        preset=nncf.QuantizationPreset.MIXED,
        subset_size=args.count,
        fast_bias_correction=True,
        ignored_scope=detection_head_scope,
    )

    # 保存
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ov.save_model(quantized_model, str(output_path))
    print(f"\n量子化モデルを保存しました: {output_path}")

    # サイズ比較
    orig_bin = model_path.with_suffix(".bin")
    out_bin = output_path.with_suffix(".bin")
    if orig_bin.exists() and out_bin.exists():
        orig_mb = orig_bin.stat().st_size / 1024**2
        out_mb = out_bin.stat().st_size / 1024**2
        ratio = (1 - out_mb / orig_mb) * 100
        print("\nサイズ比較:")
        print(f"  元モデル  : {orig_mb:.1f} MB")
        print(f"  量子化後  : {out_mb:.1f} MB")
        print(f"  削減率    : {ratio:.1f}%")


if __name__ == "__main__":
    main()

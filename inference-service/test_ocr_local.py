"""
ローカル OCR テストスクリプト
変換した OpenVINO モデルで OCR の精度を検証する

Usage:
    uv run python test_ocr_local.py <image_path>
    uv run python test_ocr_local.py <image_path> --line-strips
    uv run python test_ocr_local.py <image_path> --max-w 640
"""

import argparse
import time

import cv2
import numpy as np
import openvino as ov
from PIL import Image

DET_MODEL = "models/paddle_detection_vino/det.xml"
REC_MODEL = "models/paddle4english_vino/rec.xml"
DICT_PATH = "models/paddle4english/dict.txt"

# 認識モデル実際の入力高さ: ONNX モデルの実形状は 48px (config.json の "32" は誤記)
TARGET_H = 48
MIN_W = 32


def load_vocab(path: str) -> list[str]:
    with open(path, encoding="utf-8") as f:
        return [""] + [line.rstrip("\n") for line in f]


def preprocess_det(img_bgr: np.ndarray, det_input_size: int = 1280):
    orig_h, orig_w = img_bgr.shape[:2]
    scale = min(det_input_size / orig_w, det_input_size / orig_h)
    new_w, new_h = int(orig_w * scale), int(orig_h * scale)

    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    resized = cv2.resize(img_rgb, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

    pad_x = (det_input_size - new_w) // 2
    pad_y = (det_input_size - new_h) // 2

    canvas = np.zeros((det_input_size, det_input_size, 3), dtype=np.float32)
    canvas[pad_y:pad_y + new_h, pad_x:pad_x + new_w] = resized.astype(np.float32)
    canvas /= 255.0

    tensor = canvas.transpose(2, 0, 1)[np.newaxis, ...]
    return tensor, new_w / orig_w, new_h / orig_h, pad_x, pad_y


def postprocess_det(
    prob_map: np.ndarray,
    orig_h: int, orig_w: int,
    scale_x: float, scale_y: float,
    pad_x: int, pad_y: int,
    thresh: float = 0.2,
    dilate_w: int = 5, dilate_h: int = 3, dilate_iter: int = 1,
    min_bbox_w: int = 25,
) -> list[tuple[int, int, int, int]]:
    score_map = prob_map[0, 0]
    binary = (score_map > thresh).astype(np.uint8) * 255

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (dilate_w, dilate_h))
    dilated = cv2.dilate(binary, kernel, iterations=dilate_iter)

    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    bboxes = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        x_orig = int((x - pad_x) / scale_x)
        y_orig = int((y - pad_y) / scale_y)
        w_orig = int(w / scale_x)
        h_orig = int(h / scale_y)

        x_min = max(0, x_orig)
        y_min = max(0, y_orig)
        x_max = min(orig_w, x_orig + w_orig)
        y_max = min(orig_h, y_orig + h_orig)

        if (x_max - x_min) < min_bbox_w or (y_max - y_min) < 5:
            continue
        bboxes.append((x_min, y_min, x_max, y_max))

    bboxes.sort(key=lambda b: b[1])
    return bboxes


def preprocess_rec(crop_bgr: np.ndarray, max_w: int = 0) -> np.ndarray:
    """max_w=0 のとき幅制限なし（動的幅）"""
    h, w = crop_bgr.shape[:2]
    if h == 0 or w == 0:
        return np.zeros((1, 3, TARGET_H, MIN_W), dtype=np.float32)

    scale = TARGET_H / h
    new_w = max(MIN_W, int(w * scale))
    if max_w > 0:
        new_w = min(new_w, max_w)

    resized = cv2.resize(crop_bgr, (new_w, TARGET_H), interpolation=cv2.INTER_LINEAR)
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32)
    rgb = (rgb - 127.5) / 127.5
    return rgb.transpose(2, 0, 1)[np.newaxis, ...]


def ctc_decode(logits: np.ndarray, vocab: list[str]) -> str:
    if logits.ndim == 3:
        logits = logits[0]
    indices = np.argmax(logits, axis=-1)
    chars = []
    prev = -1
    for idx in indices:
        if idx != prev:
            if idx != 0 and idx < len(vocab):
                chars.append(vocab[idx])
            prev = idx
    return "".join(chars)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("image", help="テスト画像パス")
    parser.add_argument("--det-input-size", type=int, default=1280)
    parser.add_argument("--thresh", type=float, default=0.2)
    parser.add_argument("--dilate-w", type=int, default=5)
    parser.add_argument("--dilate-h", type=int, default=3)
    parser.add_argument("--dilate-iter", type=int, default=1)
    parser.add_argument("--max-w", type=int, default=0, help="認識モデル最大幅 (0=制限なし)")
    parser.add_argument("--line-strips", action="store_true", help="ラインストリップ分割モード")
    parser.add_argument("--strip-height", type=int, default=35, help="ストリップ高さ (px)")
    parser.add_argument("--min-bbox-w", type=int, default=25)
    args = parser.parse_args()

    print("=== OCR ローカルテスト ===")
    print(f"画像: {args.image}")
    print(f"det_input_size={args.det_input_size}, thresh={args.thresh}")
    print(f"dilate=({args.dilate_w},{args.dilate_h})×{args.dilate_iter}")
    print(f"max_w={'制限なし' if args.max_w == 0 else args.max_w}, target_h={TARGET_H}")
    print(f"line_strips={'有効' if args.line_strips else '無効'}, strip_height={args.strip_height}")
    print()

    vocab = load_vocab(DICT_PATH)
    print(f"vocab: {len(vocab)} エントリ")

    core = ov.Core()

    det_model = core.read_model(DET_MODEL)
    compiled_det = core.compile_model(det_model, "CPU", {"PERFORMANCE_HINT": "LATENCY"})

    rec_model = core.read_model(REC_MODEL)
    compiled_rec = core.compile_model(rec_model, "CPU", {"PERFORMANCE_HINT": "LATENCY"})

    img = Image.open(args.image).convert("RGB")
    img_bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    orig_h, orig_w = img_bgr.shape[:2]
    print(f"画像サイズ: {orig_w}×{orig_h}px\n")

    t0 = time.time()

    # --- 検出 ---
    tensor, sx, sy, px, py = preprocess_det(img_bgr, args.det_input_size)
    det_req = compiled_det.create_infer_request()
    det_req.infer({0: tensor})
    out_key = list(det_req.results.keys())[0]
    prob_map = det_req.results[out_key]

    bboxes = postprocess_det(
        prob_map, orig_h, orig_w, sx, sy, px, py,
        thresh=args.thresh,
        dilate_w=args.dilate_w, dilate_h=args.dilate_h, dilate_iter=args.dilate_iter,
        min_bbox_w=args.min_bbox_w,
    )
    det_time = time.time() - t0
    print(f"検出: {len(bboxes)} bbox ({det_time:.2f}s)")
    for i, (x1, y1, x2, y2) in enumerate(bboxes[:10]):
        print(f"  [{i}] ({x1},{y1})-({x2},{y2}) size={x2-x1}×{y2-y1}px")
    if len(bboxes) > 10:
        print(f"  ... 残り {len(bboxes)-10} 件")
    print()

    # --- 認識 ---
    rec_req = compiled_rec.create_infer_request()
    lines = []

    def recognize_crop(crop_bgr: np.ndarray) -> str:
        tensor = preprocess_rec(crop_bgr, args.max_w)
        rec_req.infer({0: tensor})
        out_key = list(rec_req.results.keys())[0]
        logits = rec_req.results[out_key]
        return ctc_decode(logits, vocab)

    t1 = time.time()

    if args.line_strips:
        # ラインストリップモード: 各 bbox を strip_height px に分割
        strip_count = 0
        for x1, y1, x2, y2 in bboxes:
            y = y1
            while y < y2:
                sy2 = min(y + args.strip_height, y2)
                strip = img_bgr[y:sy2, x1:x2]
                if strip.size > 0:
                    text = recognize_crop(strip)
                    if text.strip():
                        lines.append(text.strip())
                    strip_count += 1
                y += args.strip_height
        print(f"ラインストリップ認識: {strip_count} strips → {len(lines)} 行")
    else:
        # 通常モード: bbox をそのまま認識
        for x1, y1, x2, y2 in bboxes:
            crop = img_bgr[y1:y2, x1:x2]
            if crop.size == 0:
                continue
            w_at_h32 = max(MIN_W, int((x2 - x1) * TARGET_H / max(1, y2 - y1)))
            if args.max_w > 0:
                w_at_h32 = min(w_at_h32, args.max_w)
            text = recognize_crop(crop)
            if text.strip():
                lines.append(text.strip())
        print(f"通常認識: {len(bboxes)} bbox → {len(lines)} 行")

    rec_time = time.time() - t1
    total_time = time.time() - t0

    print(f"認識時間: {rec_time:.2f}s, 合計: {total_time:.2f}s\n")
    print("=== 抽出テキスト ===")
    print("\n".join(lines))


if __name__ == "__main__":
    main()

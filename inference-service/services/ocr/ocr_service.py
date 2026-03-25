"""
PaddleOCR OpenVINO OCR サービス

テキスト検出（DB モデル）とテキスト認識（CRNN モデル）を OpenVINO で実行し、
画像からテキストを抽出する。スキャン PDF のフォールバック OCR として使用。
"""

import io
import os
import queue

import cv2
import numpy as np
import openvino as ov
from PIL import Image

from common import settings
from common.logger import logger


class PaddleOpenVinoOcrService:
    """PaddleOCR（OpenVINO バックエンド）を使ったテキスト検出・認識サービス。"""

    def __init__(self) -> None:
        self.det_model_path: str = settings.get(
            "OCR_DET_MODEL_PATH",
            "/app/models/paddle_detection/det.xml",
        )
        self.rec_model_path: str = settings.get(
            "OCR_REC_MODEL_PATH",
            "/app/models/paddle4english/rec.xml",
        )
        self.dict_path: str = settings.get(
            "OCR_DICT_PATH",
            "/app/models/paddle4english/dict.txt",
        )

        # 検出モデルのハイパーパラメータ
        # 入力解像度: 大きいほど細かい文字を検出できるが推論時間が増加する
        # 学術論文(150dpi, ~1241x1630px)では1280が最適バランス
        self.det_input_size: int = int(settings.get("OCR_DET_INPUT_SIZE", "1280"))
        # DB二値化閾値: 低いほど薄い文字を拾うが誤検出も増える (0.15〜0.35)
        self.det_thresh: float = float(settings.get("OCR_DET_THRESH", "0.2"))
        # 膨張カーネルサイズ (W, H): 大きいほど単語を行単位にまとめる
        # 行全体をまとめると認識モデルのmax_wで圧縮され精度低下するため小さく設定
        self.det_dilate_ksize_w: int = int(settings.get("OCR_DET_DILATE_KSIZE_W", "20"))
        self.det_dilate_ksize_h: int = int(settings.get("OCR_DET_DILATE_KSIZE_H", "3"))
        # 膨張繰り返し回数
        self.det_dilate_iter: int = int(settings.get("OCR_DET_DILATE_ITER", "2"))
        # 最小 bbox 幅: 単一文字レベルの細切れ検出を排除する閾値（px, 1280px 入力換算）
        self.det_min_bbox_width: int = int(settings.get("OCR_DET_MIN_BBOX_WIDTH", "25"))

        self.compiled_det = None
        self.compiled_rec = None
        self.det_request_pool: queue.Queue = queue.Queue()
        self.rec_request_pool: queue.Queue = queue.Queue()

        self.vocab: list[str] = []
        self._load_dict()
        self._initialize_model()

    def _load_dict(self) -> None:
        """辞書ファイルを読み込んで CTC デコード用の vocab を構築する。"""
        if not os.path.exists(self.dict_path):
            logger.warning(f"OCR dict file not found: {self.dict_path}")
            return
        with open(self.dict_path, encoding="utf-8") as f:
            # 行0をブランクトークン（空文字）として扱い、各行を1文字として登録
            self.vocab = [""] + [line.rstrip("\n") for line in f]
        logger.info(f"OCR vocab loaded: {len(self.vocab)} entries")

    def _initialize_model(self) -> None:
        """OpenVINO で検出モデルと認識モデルをロードする。"""
        if not os.path.exists(self.det_model_path):
            logger.error(f"OCR det model not found: {self.det_model_path}")
            return
        if not os.path.exists(self.rec_model_path):
            logger.error(f"OCR rec model not found: {self.rec_model_path}")
            return

        logger.info("Initializing PaddleOpenVinoOcrService...")

        core = ov.Core()
        cache_dir = settings.get("OV_CACHE_DIR", ".ov_cache")
        os.makedirs(cache_dir, exist_ok=True)
        core.set_property({"CACHE_DIR": cache_dir})

        det_pool_size: int = int(settings.get("OCR_DET_POOL_SIZE", "1"))
        rec_pool_size: int = int(settings.get("OCR_REC_POOL_SIZE", "1"))

        # 検出モデル: LATENCY モード（クロップ逐次処理のため並列不要、メモリ節約）
        det_model = core.read_model(self.det_model_path)
        self.compiled_det = core.compile_model(
            det_model, "CPU", {"PERFORMANCE_HINT": "LATENCY"}
        )
        for _ in range(det_pool_size):
            self.det_request_pool.put(self.compiled_det.create_infer_request())

        # 認識モデル: LATENCY モード（同上）
        rec_model = core.read_model(self.rec_model_path)
        self.compiled_rec = core.compile_model(
            rec_model, "CPU", {"PERFORMANCE_HINT": "LATENCY"}
        )
        for _ in range(rec_pool_size):
            self.rec_request_pool.put(self.compiled_rec.create_infer_request())

        logger.info("PaddleOpenVinoOcrService initialized successfully")

    # ------------------------------------------------------------------
    # 検出パイプライン
    # ------------------------------------------------------------------

    def _preprocess_det(
        self, img_bgr: np.ndarray
    ) -> tuple[np.ndarray, float, float, int, int]:
        """検出モデル用の前処理。OCR_DET_INPUT_SIZE にリサイズして正規化する。

        モデルは動的入力サイズ対応のため、OCR_DET_INPUT_SIZE で解像度を制御できる。
        学術論文など高密度テキストでは 1280 が 640 より大幅に精度向上する。

        Returns:
            (tensor, scale_x, scale_y, pad_x, pad_y)
        """
        orig_h, orig_w = img_bgr.shape[:2]
        target = self.det_input_size

        scale = min(target / orig_w, target / orig_h)
        new_w = int(orig_w * scale)
        new_h = int(orig_h * scale)

        # config.json: "RGB image" → BGR→RGB 変換
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(img_rgb, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

        pad_x = (target - new_w) // 2
        pad_y = (target - new_h) // 2

        canvas = np.zeros((target, target, 3), dtype=np.float32)
        canvas[pad_y : pad_y + new_h, pad_x : pad_x + new_w] = resized.astype(
            np.float32
        )

        # config.json: "normalized to [0, 1]"
        canvas /= 255.0

        # (H,W,C) → (1,C,H,W)
        tensor = canvas.transpose(2, 0, 1)[np.newaxis, ...]

        scale_x = new_w / orig_w
        scale_y = new_h / orig_h

        return tensor, scale_x, scale_y, pad_x, pad_y

    def _postprocess_det(
        self,
        prob_map: np.ndarray,
        orig_h: int,
        orig_w: int,
        scale_x: float,
        scale_y: float,
        pad_x: int,
        pad_y: int,
    ) -> list[tuple[int, int, int, int]]:
        """DB モデルの確率マップをテキスト領域の bbox リストに変換する。

        ハイパーパラメータは設定ファイルで制御:
          OCR_DET_THRESH         二値化閾値 (default: 0.2)
          OCR_DET_DILATE_KSIZE_W 膨張カーネル幅 (default: 3)
          OCR_DET_DILATE_KSIZE_H 膨張カーネル高さ (default: 2)
          OCR_DET_DILATE_ITER    膨張繰り返し回数 (default: 1)

        Returns:
            [(x_min, y_min, x_max, y_max), ...] のリスト（Y 座標昇順）
        """
        score_map = prob_map[0, 0]

        # 二値化
        binary = (score_map > self.det_thresh).astype(np.uint8) * 255

        # 膨張してテキスト領域をつなげる
        kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT,
            (self.det_dilate_ksize_w, self.det_dilate_ksize_h),
        )
        dilated = cv2.dilate(binary, kernel, iterations=self.det_dilate_iter)

        contours, _ = cv2.findContours(
            dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        bboxes: list[tuple[int, int, int, int]] = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)

            # パディング・スケールを逆変換して元画像座標に戻す
            x_orig = int((x - pad_x) / scale_x)
            y_orig = int((y - pad_y) / scale_y)
            w_orig = int(w / scale_x)
            h_orig = int(h / scale_y)

            x_min = max(0, x_orig)
            y_min = max(0, y_orig)
            x_max = min(orig_w, x_orig + w_orig)
            y_max = min(orig_h, y_orig + h_orig)

            # 小さすぎる領域を除外（単一文字レベルの細切れ検出を排除）
            if (x_max - x_min) < self.det_min_bbox_width or (y_max - y_min) < 5:
                continue

            bboxes.append((x_min, y_min, x_max, y_max))

        # Y 座標（読み取り順）でソート
        bboxes.sort(key=lambda b: b[1])
        return bboxes

    def _detect_text_regions(
        self, img_bgr: np.ndarray
    ) -> list[tuple[int, int, int, int]]:
        """検出モデルを使ってテキスト領域の bbox を返す。"""
        if self.compiled_det is None:
            return []

        orig_h, orig_w = img_bgr.shape[:2]
        tensor, scale_x, scale_y, pad_x, pad_y = self._preprocess_det(img_bgr)

        infer_req = self.det_request_pool.get()
        try:
            infer_req.infer({0: tensor})
            # 出力は通常 (1, 1, H, W) の確率マップ
            output_key = list(infer_req.results.keys())[0]
            prob_map = infer_req.results[output_key]
        finally:
            self.det_request_pool.put(infer_req)

        return self._postprocess_det(
            prob_map, orig_h, orig_w, scale_x, scale_y, pad_x, pad_y
        )

    # ------------------------------------------------------------------
    # 認識パイプライン
    # ------------------------------------------------------------------

    def _preprocess_rec(self, crop_bgr: np.ndarray) -> np.ndarray:
        """認識モデル用の前処理。高さ 48px に正規化する（PP-OCRv5 実モデル仕様）。

        PP-OCRv5 (SVTRv2) は動的幅対応のため max_w 制限は設けない。
        幅は最低 32px 必要（AveragePool の kernel 幅が縮小後に 1 以下になるのを防ぐ）。
        """
        target_h = 48
        min_w = 32   # AveragePool の kernel 幅が縮小後に 1 以下になるのを防ぐ

        h, w = crop_bgr.shape[:2]
        if h == 0 or w == 0:
            return np.zeros((1, 3, target_h, min_w), dtype=np.float32)

        scale = target_h / h
        new_w = max(min_w, int(w * scale))

        resized = cv2.resize(crop_bgr, (new_w, target_h), interpolation=cv2.INTER_LINEAR)

        # config.json: "Grayscale or RGB image" → BGR→RGB 変換して 3ch RGB で渡す
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32)

        # config.json: "normalized" → mean=0.5, std=0.5（PP-OCRv5 CRNN 標準）
        # (x / 255 - 0.5) / 0.5 = (x - 127.5) / 127.5
        rgb = (rgb - 127.5) / 127.5

        # (H,W,C) → (1,C,H,W)
        return rgb.transpose(2, 0, 1)[np.newaxis, ...]

    def _ctc_decode(self, logits: np.ndarray) -> str:
        """CTC グリーディデコード。

        Args:
            logits: config.json の output_shape に従い (batch_size, sequence_length, num_classes)
                    つまり (1, T, num_classes)
        Returns:
            デコードされたテキスト文字列
        """
        if logits.ndim == 3:
            logits = logits[0]  # (1, T, num_classes) → (T, num_classes)

        indices = np.argmax(logits, axis=-1)  # (T,)

        # 連続重複除去 + ブランク（index 0）除去
        chars: list[str] = []
        prev = -1
        for idx in indices:
            if idx != prev:
                if idx != 0 and idx < len(self.vocab):
                    chars.append(self.vocab[idx])
                prev = idx

        return "".join(chars)

    def _recognize_text(self, crop_bgr: np.ndarray) -> str:
        """クロップ画像からテキストを認識する。"""
        if self.compiled_rec is None or not self.vocab:
            return ""

        tensor = self._preprocess_rec(crop_bgr)

        infer_req = self.rec_request_pool.get()
        try:
            infer_req.infer({0: tensor})
            output_key = list(infer_req.results.keys())[0]
            logits = infer_req.results[output_key]
        finally:
            self.rec_request_pool.put(infer_req)

        return self._ctc_decode(logits)

    # ------------------------------------------------------------------
    # 公開 API
    # ------------------------------------------------------------------

    def ocr_page(
        self,
        img_bytes: bytes,
        bboxes: list[dict] | None = None,
    ) -> str:
        """ページ画像からテキストを抽出する。

        Args:
            img_bytes: JPEG/PNG 等の画像バイト
            bboxes: テキスト領域のリスト（省略時は検出モデルで自動検出）
                    各要素は {"x_min": int, "y_min": int, "x_max": int, "y_max": int}
        Returns:
            認識テキスト（改行区切り）
        """
        # PIL → OpenCV BGR
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        img_bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        orig_h, orig_w = img_bgr.shape[:2]

        # テキスト領域を決定
        if bboxes:
            regions: list[tuple[int, int, int, int]] = [
                (
                    int(b.get("x_min", 0)),
                    int(b.get("y_min", 0)),
                    int(b.get("x_max", orig_w)),
                    int(b.get("y_max", orig_h)),
                )
                for b in bboxes
            ]
            regions.sort(key=lambda b: b[1])
        else:
            regions = self._detect_text_regions(img_bgr)

        if not regions:
            return ""

        lines: list[str] = []
        for x_min, y_min, x_max, y_max in regions:
            crop = img_bgr[y_min:y_max, x_min:x_max]
            if crop.size == 0:
                continue
            text = self._recognize_text(crop)
            if text.strip():
                lines.append(text.strip())

        return "\n".join(lines)

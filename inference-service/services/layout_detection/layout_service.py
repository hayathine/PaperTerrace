"""
レイアウト解析サービス
PP-DocLayout-L を使用したONNX推論による図表・数式検出
"""

import os
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import onnxruntime as ort
from pydantic import BaseModel

from common.logger import logger


class BBox(BaseModel):
    """バウンディングボックス"""

    x_min: float
    y_min: float
    x_max: float
    y_max: float

    @classmethod
    def from_list(cls, coord: list[float]) -> "BBox":
        return cls(
            x_min=coord[0],
            y_min=coord[1],
            x_max=coord[2],
            y_max=coord[3],
        )


class LayoutItem(BaseModel):
    """レイアウト要素"""

    bbox: BBox
    class_name: str
    score: float


class LayoutAnalysisService:
    """レイアウト解析サービス"""

    # ラベルマップ (PP-DocLayoutの標準クラス)
    LABELS = [
        "Text",
        "Title",
        "Figure",
        "Figure caption",
        "Table",
        "Table caption",
        "Header",
        "Footer",
        "Reference",
        "Equation",
    ]

    def __init__(self, lang: str = "en", model_path: str | None = None):
        """
        Parameters
        ----------
        lang: str
            言語コード (未使用だがインターフェース互換のため)
        model_path : str | None
            ONNXモデルファイルのパス。Noneの場合はデフォルトパスを使用
        """
        if model_path is None:
            # デフォルトモデルパス
            model_path = os.getenv(
                "LAYOUT_MODEL_PATH",
                "/app/models/paddle2onnx/PP-DocLayout-L_infer.onnx",
            )

        self.model_path = model_path
        self.session = None
        self.image_input_name = None
        self.scale_input_name = None
        self.im_shape_input_name = None

        self._initialize_model()

    def _initialize_model(self):
        """モデルを初期化"""
        logger.info("Initializing LayoutAnalysisService...")
        logger.info(f"Model path: {self.model_path}")

        # モデルファイルの存在確認
        if not os.path.exists(self.model_path):
            # ローカル開発などでパスが違う場合のフォールバック（よしなに）
            local_fallback = (
                "inference-service/models/paddle2onnx/PP-DocLayout-L_infer.onnx"
            )
            if os.path.exists(local_fallback):
                self.model_path = local_fallback
                logger.info(f"Using local fallback model path: {self.model_path}")
            elif os.path.exists("../models/paddle2onnx/PP-DocLayout-L_infer.onnx"):
                self.model_path = "../models/paddle2onnx/PP-DocLayout-L_infer.onnx"
                logger.info(f"Using relative fallback model path: {self.model_path}")
            else:
                # ファイルがない場合はエラーにするが、開発環境向けにWARNINGで止める手もある
                logger.error(f"Model file not found: {self.model_path}")
                # raise FileNotFoundError(f"Model file not found: {self.model_path}")
                # 一旦、モデルがなくても起動するようにreturnする（ただし推論は失敗する）
                return

        try:
            # モデルファイルサイズを取得
            model_size_mb = os.path.getsize(self.model_path) / (1024 * 1024)
            logger.info(f"Model file size: {model_size_mb:.2f} MB")

            # CPU情報を取得
            cpu_count = os.cpu_count()
            logger.info(f"Available CPU cores: {cpu_count}")

            # ONNXランタイムのセッションオプション設定
            session_options = ort.SessionOptions()
            session_options.intra_op_num_threads = cpu_count or 4
            session_options.inter_op_num_threads = 1
            session_options.log_severity_level = 3  # WARNING以上のみ

            logger.info(
                f"ONNX session config - intra_op_threads: {cpu_count}, inter_op_threads: 1"
            )

            # 推論セッションの初期化
            self.session = ort.InferenceSession(
                self.model_path,
                providers=["CPUExecutionProvider"],
                sess_options=session_options,
            )

            # モデル情報をログ出力
            inputs = self.session.get_inputs()
            self.session.get_outputs()

            # 入力名を特定
            for input_info in inputs:
                if input_info.name == "image":
                    self.image_input_name = input_info.name
                elif input_info.name == "scale_factor":
                    self.scale_input_name = input_info.name
                elif input_info.name == "im_shape":
                    self.im_shape_input_name = input_info.name

            if not self.image_input_name:
                self.image_input_name = inputs[0].name

            logger.info("LayoutAnalysisService initialization completed")
        except Exception as e:
            logger.error(f"Failed to initialize LayoutAnalysisService: {e}")
            self.session = None

    async def analyze_async(self, pdf_path: str) -> list[dict]:
        """PDF解析（スタブのまま維持、あるいは実装が必要なら実装するが今回は画像解析が主）"""
        # 今回の要件は画像解析のエンドポイント追加なので、ここは一旦スタブのままか、既存のままにしておく
        return []

    def analyze_image(self, image_path: str | Path) -> list[LayoutItem]:
        """
        画像からレイアウト要素を検出

        Parameters
        ----------
        image_path : str | Path
            解析対象の画像ファイルパス

        Returns
        -------
        list[LayoutItem]
            検出されたレイアウト要素のリスト
        """
        if self.session is None:
            logger.error("Model is not initialized via session")
            raise RuntimeError("LayoutAnalysisService is not properly initialized")

        logger.info(f"Starting layout analysis for: {image_path}")
        start_time = time.time()

        try:
            img, ori_shape, scale_factor = self._preprocess(image_path)

            # im_shapeを準備（元画像のサイズ）
            im_shape = np.array(
                [[ori_shape[0], ori_shape[1]]], dtype=np.float32
            )  # [height, width]

            outputs = self._inference(img, scale_factor, im_shape)
            results = self._postprocess(outputs, ori_shape)

            total_time = time.time() - start_time
            logger.info(
                f"Total analysis time: {total_time:.3f}s. Detected {len(results)} elements"
            )

            # LayoutItemオブジェクトに変換
            layout_items = []
            for result in results:
                bbox = BBox.from_list(result["bbox"])
                class_id = result["class_id"]
                class_name = (
                    self.LABELS[class_id]
                    if class_id < len(self.LABELS)
                    else f"Unknown({class_id})"
                )
                layout_items.append(
                    LayoutItem(bbox=bbox, class_name=class_name, score=result["score"])
                )

            return layout_items

        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            raise

    def _preprocess(
        self, img_path: str | Path, target_size: tuple[int, int] = (640, 640)
    ) -> tuple[np.ndarray, tuple[int, int], np.ndarray]:
        """画像前処理"""
        # 画像の読み込み
        img = cv2.imread(str(img_path))
        if img is None:
            raise FileNotFoundError(f"Could not load image: {img_path}")

        ori_h, ori_w = img.shape[:2]

        # BGR to RGB
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        # リサイズ
        img = cv2.resize(img, target_size)

        # Scale factor (h, w)
        scale_h = target_size[1] / ori_h
        scale_w = target_size[0] / ori_w
        scale_factor = np.array([scale_h, scale_w], dtype=np.float32).reshape((1, 2))

        # 正規化 (PaddleOCRの標準設定)
        img = img.astype(np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        img = (img - mean) / std

        # HWC to CHW & Batch dimension
        img = img.transpose(2, 0, 1)
        img = np.expand_dims(img, axis=0).astype(np.float32)

        return img, (ori_h, ori_w), scale_factor

    def _inference(
        self,
        preprocessed_img: np.ndarray,
        scale_factor: np.ndarray,
        im_shape: np.ndarray,
    ) -> list:
        """ONNX推論実行"""
        # 入力データを準備
        input_feed = {}

        if self.image_input_name:
            input_feed[self.image_input_name] = preprocessed_img
        if self.scale_input_name:
            input_feed[self.scale_input_name] = scale_factor
        if self.im_shape_input_name:
            input_feed[self.im_shape_input_name] = im_shape

        outputs = self.session.run(None, input_feed)
        return outputs

    def _postprocess(
        self,
        outputs: list,
        ori_shape: tuple[int, int],
        target_size: tuple[int, int] = (640, 640),
        threshold: float = 0.5,
    ) -> list[dict[str, Any]]:
        """後処理：座標変換とフィルタリング"""
        predictions = outputs[0]
        ori_h, ori_w = ori_shape

        # 有効な予測を抽出
        valid_mask = predictions[:, 1] >= threshold
        valid_predictions = predictions[valid_mask]

        results = []

        if len(valid_predictions) > 0:
            # スケールファクターを決定
            scale_x = target_size[0] / ori_w
            scale_y = target_size[1] / ori_h

            for res in valid_predictions:
                class_id, score, xmin, ymin, xmax, ymax = res

                # 座標を元のサイズに復元
                x1 = max(0, min(ori_w, int(xmin * scale_x)))
                y1 = max(0, min(ori_h, int(ymin * scale_y)))
                x2 = max(0, min(ori_w, int(xmax * scale_x)))
                y2 = max(0, min(ori_h, int(ymax * scale_y)))

                box = [x1, y1, x2, y2]

                if box[2] > box[0] and box[3] > box[1]:
                    results.append(
                        {"class_id": int(class_id), "score": float(score), "bbox": box}
                    )

        return results

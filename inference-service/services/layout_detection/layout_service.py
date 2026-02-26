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

from common.logger import logger
from common.schemas.layout import LABELS, BBoxModel, LayoutItem
from services.layout_detection.preprocess import (
    LetterBoxResize,
    NormalizeImage,
    Permute,
    preprocess,
)


class LayoutAnalysisService:
    """レイアウト解析サービス"""

    # ラベルマップ
    LABELS = LABELS

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
        self.engine = "ONNX"

        self._initialize_model()

    def _initialize_model(self):
        """モデルを初期化"""
        logger.info("Initializing LayoutAnalysisService (Backend: ONNX)...")
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
            session_options.graph_optimization_level = (
                ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            )
            session_options.intra_op_num_threads = min(cpu_count or 4, 8)
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
            img, ori_shape, scale, pad_info = self._preprocess(image_path)

            # im_shape を準備（モデル入力サイズ）
            im_shape = np.array([[img.shape[2], img.shape[3]]], dtype=np.float32)

            # scale_factor を準備 (1.0, 1.0 にして後処理で自前で計算する方式に統一)
            scale_factor = np.array([[1.0, 1.0]], dtype=np.float32)

            outputs = self._inference(img, scale_factor, im_shape)
            results = self._postprocess(
                outputs, ori_shape, scale=scale, pad_info=pad_info
            )

            total_time = time.time() - start_time
            logger.info(
                f"Total analysis time: {total_time:.3f}s. Detected {len(results)} elements"
            )

            # LayoutItemオブジェクトに変換
            layout_items = []
            for result in results:
                bbox = BBoxModel.from_list(result["bbox"])
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
    ) -> tuple[np.ndarray, tuple[int, int], float, np.ndarray]:
        """画像前処理"""
        # 画像の読み込み
        img_bgr = cv2.imread(str(img_path))
        if img_bgr is None:
            raise FileNotFoundError(f"Could not load image: {img_path}")

        ori_h, ori_w = img_bgr.shape[:2]
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

        # 統一されたプリプロセッサを使用
        ops = [
            LetterBoxResize(target_size=target_size),
            NormalizeImage(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
                is_scale=True,
                norm_type="mean_std",
            ),
            Permute(),
        ]

        processed_img, info = preprocess(img_rgb, ops)

        # Batch dimension
        processed_img = np.expand_dims(processed_img, axis=0).astype(np.float32)

        scale = info["scale_factor"][0]  # new_w / ori_w
        pad_info = info["pad_info"]  # [pad_h, pad_w]

        logger.info(
            f"Preprocess complete - ori_shape: {ori_h}x{ori_w}, scale: {scale:.4f}, pad: {pad_info}"
        )

        return processed_img, (ori_h, ori_w), scale, pad_info

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

        logger.info(f"Inference - input_feed keys: {list(input_feed.keys())}")
        for k, v in input_feed.items():
            logger.info(f"Inference - input '{k}' shape: {v.shape}, dtype: {v.dtype}")

        outputs = self.session.run(None, input_feed)
        return outputs

    def _postprocess(
        self,
        outputs: list,
        ori_shape: tuple[int, int],
        target_size: tuple[int, int] = (640, 640),
        threshold: float = 0.5,
        scale: float = 1.0,
        pad_info: np.ndarray | None = None,
    ) -> list[dict[str, Any]]:
        """後処理：座標変換とフィルタリング

        モデル出力の座標は640x640スケールで返されるため、
        元画像のピクセル座標に変換する必要がある。
        """
        # Ensure threshold is float
        if isinstance(threshold, str):
            try:
                threshold = float(threshold)
            except ValueError:
                logger.warning(
                    f"Invalid threshold value: {threshold}. Using default 0.9"
                )
                threshold = 0.9

        predictions = outputs[0]
        ori_h, ori_w = ori_shape

        # パディング情報を取得
        pad_h, pad_w = (0.0, 0.0)
        if pad_info is not None:
            pad_h, pad_w = pad_info

        logger.debug(
            f"[Layout] Postprocess: scale={scale:.4f}, pad=({pad_h}, {pad_w}), ori={ori_w}x{ori_h}"
        )

        # デバッグログ追加: 推論データの生の状態を確認
        logger.info(f"Postprocess - predictions shape: {predictions.shape}")
        if predictions.shape[0] > 0:
            max_score = np.max(predictions[:, 1])
            logger.info(f"Postprocess - max score in all predictions: {max_score:.4f}")

            # スコアの分布を確認
            for t in [0.1, 0.2, 0.3, 0.4, 0.5]:
                count = np.sum(predictions[:, 1] >= t)
                logger.info(
                    f"Postprocess - elements count above threshold {t}: {count}"
                )

            # 上位5つの生データを詳しく出力 (座標系の把握のため)
            top_indices = np.argsort(predictions[:, 1])[-5:][::-1]
            for i, idx in enumerate(top_indices):
                p = predictions[idx]
                logger.info(
                    f"Postprocess - top {i + 1} prediction: class_id={int(p[0])}, score={p[1]:.4f}, raw_bbox={p[2:]}"
                )

        # 有効な予測を抽出
        valid_mask = predictions[:, 1] >= threshold
        valid_predictions = predictions[valid_mask]

        results = []

        if len(valid_predictions) > 0:
            # モデル出力は640x640スケールの座標なので、元画像スケールに変換
            # scale_factor = 640 / ori_w なので、元に戻すには / scale_factor (= * ori_w / 640)

            for res in valid_predictions:
                class_id, score, xxmin, yymin, xxmax, yymax = res

                # モデル出力は 640x640 等のキャンバス座標系
                # 1. パディングを除去
                # 2. スケールを元に戻す
                x1 = max(0, min(ori_w, int((xxmin - pad_w) / scale)))
                y1 = max(0, min(ori_h, int((yymin - pad_h) / scale)))
                x2 = max(0, min(ori_w, int((xxmax - pad_w) / scale)))
                y2 = max(0, min(ori_h, int((yymax - pad_h) / scale)))

                logger.debug(
                    f"Postprocess - Coordinates: ({xxmin:.1f}, {yymin:.1f}, {xxmax:.1f}, {yymax:.1f}) -> Final: ({x1}, {y1}, {x2}, {y2})"
                )

                box = [x1, y1, x2, y2]

                if box[2] > box[0] and box[3] > box[1]:
                    final_class_id = int(class_id)
                    results.append(
                        {
                            "class_id": final_class_id,
                            "score": float(score),
                            "bbox": box,
                        }
                    )
        return self._apply_nms(results)

    def _apply_nms(
        self,
        results: list[dict],
        iou_threshold: float = 0.5,
        ioa_threshold: float = 0.8,
    ) -> list[dict]:
        if not results:
            return []

        boxes = np.array([r["bbox"] for r in results])
        scores = np.array([r["score"] for r in results])

        x1 = boxes[:, 0]
        y1 = boxes[:, 1]
        x2 = boxes[:, 2]
        y2 = boxes[:, 3]

        areas = (x2 - x1) * (y2 - y1)
        # ゼロ割りなど防止
        areas[areas <= 0] = 1e-6

        order = scores.argsort()[::-1]
        keep = []

        while order.size > 0:
            i = order[0]
            keep.append(i)

            if order.size == 1:
                break

            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])

            w = np.maximum(0.0, xx2 - xx1)
            h = np.maximum(0.0, yy2 - yy1)
            inter = w * h

            ovr = inter / (areas[i] + areas[order[1:]] - inter)
            ioa = inter / np.minimum(areas[i], areas[order[1:]])

            # IoU閾値以下、かつIoA閾値以下のものを残す
            inds = np.where((ovr <= iou_threshold) & (ioa <= ioa_threshold))[0]
            order = order[inds + 1]

        return [results[i] for i in keep]

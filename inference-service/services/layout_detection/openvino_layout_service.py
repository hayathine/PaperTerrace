import os
import queue
import time
from pathlib import Path
from typing import Any

import numpy as np
import openvino as ov

from common.logger import logger
from common.schemas.layout import LABELS, BBoxModel, LayoutItem
from services.layout_detection.preprocess import (
    LetterBoxResize,
    NormalizeImage,
    Permute,
    preprocess,
)


class OpenVINOLayoutAnalysisService:
    """OpenVINOを使用したレイアウト解析サービス"""

    LABELS = LABELS

    def __init__(self, lang: str = "en", model_path: str | None = None):
        if model_path is None:
            model_path = os.getenv(
                "LAYOUT_OPENVINO_MODEL_PATH",
                "/home/gwsgs/work_space/llm-server/models/paddl2vino/PP-DocLayout-L_infer.xml",
            )
        self.model_path = model_path
        self.compiled_model = None
        self.request_pool = queue.Queue()
        self.image_input_name = None

        self.preprocess_ops = [
            LetterBoxResize(target_size=(640, 640)),
            NormalizeImage(
                mean=[0.0, 0.0, 0.0],
                std=[1.0, 1.0, 1.0],
                is_scale=True,
                norm_type="none",
            ),
            Permute(),
        ]

        self.engine = "OpenVINO"

        self._initialize_model()

    def _initialize_model(self):
        logger.info("Initializing OpenVINOLayoutAnalysisService (Backend: OpenVINO)...")
        logger.info(f"Model path: {self.model_path}")

        if not os.path.exists(self.model_path):
            logger.error(f"Model file not found: {self.model_path}")
            return

        try:
            core = ov.Core()

            # モデルロード高速化のためのキャッシュ設定
            cache_dir = os.getenv("OV_CACHE_DIR", ".ov_cache")
            os.makedirs(cache_dir, exist_ok=True)
            core.set_property({"CACHE_DIR": cache_dir})

            model = core.read_model(model=self.model_path)

            # OpenVINO パフォーマンス最適化
            config = {
                "PERFORMANCE_HINT": "THROUGHPUT",
                "NUM_STREAMS": "AUTO",
            }

            self.compiled_model = core.compile_model(
                model=model, device_name="CPU", config=config
            )

            # 環境変数を用いた最適化ルール（OMP_NUM_THREADS、スレッド/ストリーム数など）に
            # 基づき、OpenVINOエンジン側が算出した「同時に実行すべき最適リクエスト数」を取得
            optimal_requests = self.compiled_model.get_property(
                "OPTIMAL_NUMBER_OF_INFER_REQUESTS"
            )
            for _ in range(optimal_requests):
                self.request_pool.put(self.compiled_model.create_infer_request())

            # 入力名の特定
            self.target_size = (640, 640)  # default

            # Reset named inputs
            self.image_input_name = None
            self.scale_input_name = None
            self.im_shape_input_name = None

            for input_node in self.compiled_model.inputs:
                names = input_node.get_names()

                # Check for image
                if "image" in names or any("image" in n for n in names):
                    self.image_input_name = input_node
                    try:
                        shape = input_node.partial_shape
                        if (
                            len(shape) >= 4
                            and shape[2].is_static
                            and shape[3].is_static
                        ):
                            self.target_size = (
                                shape[2].get_length(),
                                shape[3].get_length(),
                            )
                            logger.info(
                                f"Dynamically set target_size to {self.target_size}"
                            )
                    except Exception as e:
                        logger.warning(f"Could not read dynamic target size: {e}")

                # Check for scale_factor
                elif "scale_factor" in names or any("scale_factor" in n for n in names):
                    self.scale_input_name = input_node

                # Check for im_shape
                elif "im_shape" in names or any("im_shape" in n for n in names):
                    self.im_shape_input_name = input_node

            if not self.image_input_name and len(self.compiled_model.inputs) > 0:
                self.image_input_name = self.compiled_model.inputs[0]

            logger.info("OpenVINOLayoutAnalysisService initialization completed")
        except Exception as e:
            logger.error(f"Failed to initialize OpenVINOLayoutAnalysisService: {e}")
            self.compiled_model = None

    def analyze_image(
        self, image_path: str | Path, target_classes: list[str] | None = None
    ) -> list[LayoutItem]:
        if self.compiled_model is None:
            raise RuntimeError("Model is not initialized")

        target_class_ids = None
        if target_classes:
            name_to_id = {v: k for k, v in self.LABELS.items()}
            target_class_ids = [
                name_to_id[name] for name in target_classes if name in name_to_id
            ]

        start_time = time.time()
        try:
            img, im_shape, scale_factor, real_pad_info, real_scale = self._preprocess(
                image_path, target_size=self.target_size
            )
            outputs = self._inference(img, scale_factor, im_shape)
            results = self._postprocess(
                outputs,
                real_scale=real_scale,
                pad_info=real_pad_info,
                threshold=0.5,
                target_class_ids=target_class_ids,
            )

            total_time = time.time() - start_time
            logger.info(
                f"Total analysis time: {total_time:.3f}s. Detected {len(results)} elements"
            )

            layout_items = []
            for result in results:
                bbox = BBoxModel.from_list(result["bbox"])
                class_id = int(result["class_id"])
                class_name = self.LABELS.get(class_id, f"Unknown({class_id})")
                layout_items.append(
                    LayoutItem(bbox=bbox, class_name=class_name, score=result["score"])
                )

            return layout_items
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            raise

    def _preprocess(
        self, img_path: str | Path, target_size: tuple[int, int] = (640, 640)
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        try:
            from PIL import Image

            img_pil = Image.open(str(img_path))
            if img_pil.mode != "RGB":
                img_pil = img_pil.convert("RGB")
            img = np.array(img_pil)
        except Exception as e:
            raise FileNotFoundError(f"Could not load image: {img_path}") from e

        # We need to temporarily update preprocess_ops to use the passed target_size
        ops = [
            LetterBoxResize(target_size=target_size),
            NormalizeImage(
                mean=[0.0, 0.0, 0.0],
                std=[1.0, 1.0, 1.0],
                is_scale=True,
                norm_type="none",
            ),
            Permute(),
        ]
        img, im_info = preprocess(img, ops)
        img = np.expand_dims(img, axis=0).astype(np.float32)

        im_shape = np.array([[img.shape[2], img.shape[3]]], dtype=np.float32)
        scale_factor = np.array([[1.0, 1.0]], dtype=np.float32)

        real_pad_info = np.expand_dims(
            im_info.get("pad_info", np.array([0, 0])), axis=0
        ).astype(np.float32)
        real_scale = np.expand_dims(im_info["scale_factor"], axis=0).astype(np.float32)

        return img, im_shape, scale_factor, real_pad_info, real_scale

    def _inference(
        self,
        preprocessed_img: np.ndarray,
        scale_factor: np.ndarray,
        im_shape: np.ndarray,
    ) -> list:
        input_feed = {}
        if self.image_input_name is not None:
            input_feed[self.image_input_name] = preprocessed_img
        if getattr(self, "scale_input_name", None) is not None:
            input_feed[self.scale_input_name] = scale_factor
        if getattr(self, "im_shape_input_name", None) is not None:
            input_feed[self.im_shape_input_name] = im_shape

        try:
            infer_request = self.request_pool.get_nowait()
        except queue.Empty:
            infer_request = self.compiled_model.create_infer_request()

        # 非同期実行し、完了を待機 (CPUコアをフル活用して並列推論)
        infer_request.start_async(input_feed)
        infer_request.wait()

        result = infer_request.results
        outputs = list(result.values())

        # 使い終わったリクエストをプールへ返却
        self.request_pool.put(infer_request)

        return outputs

    def _postprocess(
        self,
        outputs: list,
        real_scale: np.ndarray,
        pad_info: np.ndarray,
        threshold: float = 0.5,
        target_class_ids: list[int] | None = None,
    ) -> list[dict[str, Any]]:
        predictions = outputs[0]
        ratio = real_scale[0][0]
        pad_h, pad_w = pad_info[0]

        valid_mask = predictions[:, 1] >= threshold
        if target_class_ids is not None:
            valid_mask &= np.isin(predictions[:, 0], target_class_ids)

        valid_predictions = predictions[valid_mask]

        results = []
        if len(valid_predictions) > 0:
            class_ids = valid_predictions[:, 0]
            scores = valid_predictions[:, 1]
            boxes = valid_predictions[:, 2:6].copy()

            logger.info(
                f"Postprocess - ratio: {ratio:.4f}, pad_h: {pad_h}, pad_w: {pad_w}"
            )
            logger.info(
                f"Postprocess - sample raw bbox (first 3): {predictions[:3, 2:6]}"
            )

            boxes[:, [0, 2]] = (boxes[:, [0, 2]] - pad_w) / ratio
            boxes[:, [1, 3]] = (boxes[:, [1, 3]] - pad_h) / ratio

            logger.info(f"Postprocess - sample transformed bbox (first 3): {boxes[:3]}")

            boxes = np.round(boxes).astype(int)
            boxes = np.maximum(boxes, 0)

            valid_box_mask = (boxes[:, 2] > boxes[:, 0]) & (boxes[:, 3] > boxes[:, 1])

            f_class_ids = class_ids[valid_box_mask]
            f_scores = scores[valid_box_mask]
            f_boxes = boxes[valid_box_mask]

            for cid, score, box in zip(f_class_ids, f_scores, f_boxes):
                results.append(
                    {
                        "class_id": int(cid),
                        "score": float(score),
                        "bbox": box.tolist(),
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

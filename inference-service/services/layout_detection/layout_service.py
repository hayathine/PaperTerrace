"""
レイアウト解析サービス（最適化版）
PaddleX を使用した軽量実装
"""

import logging
import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort
from pydantic import BaseModel

# ログ設定（標準出力）
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


class BBox(BaseModel):
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
    bbox: BBox
    score: float | None = None


class LayoutAnalysisService:
    """レイアウト解析サービス"""

    def __init__(
        self,
        image_path: str,
        model_path: str = "./models/paddle2onnx/PP-DocLayout-M_infer.onnx",
        lang: str = "en",
        model_dir="PP-DocLayout-M_infer",
    ) -> None:

        logger.info(f"Initializing LayoutAnalysisService...")
        logger.info(f"Model path: {model_path}")
        logger.info(f"Image path: {image_path}")
        logger.info(f"Language: {lang}")
        
        # モデルファイルの存在確認
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")
        
        # モデルファイルサイズを取得
        model_size_mb = os.path.getsize(model_path) / (1024 * 1024)
        logger.info(f"Model file size: {model_size_mb:.2f} MB")

        # CPU情報を取得
        cpu_count = os.cpu_count()
        logger.info(f"Available CPU cores: {cpu_count}")
        
        # ONNXランタイムのセッションオプション設定
        session_options = ort.SessionOptions()
        session_options.intra_op_num_threads = cpu_count  # CPU並列処理数を設定
        session_options.inter_op_num_threads = 1  # オペレータ間の並列処理数
        session_options.log_severity_level = 3  # ログレベル（3=WARNING以上のみ）
        
        logger.info(f"ONNX session config - intra_op_threads: {cpu_count}, inter_op_threads: 1")

        # 推論セッションの初期化
        self.session = ort.InferenceSession(
            model_path, 
            providers=["CPUExecutionProvider"],
            sess_options=session_options
        )
        
        # モデル情報をログ出力
        inputs = self.session.get_inputs()
        outputs = self.session.get_outputs()
        
        logger.info(f"Model has {len(inputs)} inputs:")
        for i, input_info in enumerate(inputs):
            logger.info(f"  Input {i}: name='{input_info.name}', shape={input_info.shape}, type={input_info.type}")
        
        logger.info(f"Model has {len(outputs)} outputs:")
        for i, output_info in enumerate(outputs):
            logger.info(f"  Output {i}: name='{output_info.name}', shape={output_info.shape}, type={output_info.type}")
        
        # 画像入力を探す（通常は最初の入力または'image'という名前）
        self.image_input_name = None
        self.scale_input_name = None
        self.im_shape_input_name = None
        
        for input_info in inputs:
            if input_info.name == 'image':
                self.image_input_name = input_info.name
                logger.info(f"Found image input: {input_info.name}")
            elif input_info.name == 'scale_factor':
                self.scale_input_name = input_info.name
                logger.info(f"Found scale_factor input: {input_info.name}")
            elif input_info.name == 'im_shape':
                self.im_shape_input_name = input_info.name
                logger.info(f"Found im_shape input: {input_info.name}")
        
        if not self.image_input_name:
            # フォールバック：最初の入力を使用
            self.image_input_name = inputs[0].name
            logger.warning(f"Could not find image input, using first input: {self.image_input_name}")
        
        logger.info(f"ONNX Runtime providers: {self.session.get_providers()}")
        
        self.image_path = image_path
        logger.info("LayoutAnalysisService initialization completed")

    def analysis(self) -> list[dict]:
        logger.info("Starting layout analysis...")
        start_time = time.time()
        
        img, ori_shape, scale_factor = self._preprocess(self.image_path)
        preprocess_time = time.time() - start_time
        logger.info(f"Preprocessing completed in {preprocess_time:.3f}s")
        
        # im_shapeを準備（元画像のサイズ）
        im_shape = np.array([[ori_shape[0], ori_shape[1]]], dtype=np.float32)  # [height, width]
        
        inference_start = time.time()
        outputs = self._inference(img, scale_factor, im_shape)
        inference_time = time.time() - inference_start
        logger.info(f"Inference completed in {inference_time:.3f}s")
        
        postprocess_start = time.time()
        results = self._postprocess(outputs, ori_shape)
        postprocess_time = time.time() - postprocess_start
        logger.info(f"Postprocessing completed in {postprocess_time:.3f}s")
        
        total_time = time.time() - start_time
        logger.info(f"Total analysis time: {total_time:.3f}s")
        logger.info(f"Detected {len(results)} layout elements")
        
        return results
        
        postprocess_start = time.time()
        results = self._postprocess(outputs, ori_shape)
        postprocess_time = time.time() - postprocess_start
        logger.info(f"Postprocessing completed in {postprocess_time:.3f}s")
        
        total_time = time.time() - start_time
        logger.info(f"Total analysis time: {total_time:.3f}s")
        logger.info(f"Detected {len(results)} layout elements")
        
        return results

    def _inference(self, preprocessed_img: np.ndarray, scale_factor: np.ndarray, im_shape: np.ndarray) -> list:
        """
        前処理済み画像から推論を実行
        """
        logger.info("Running ONNX inference...")

        try:
            # 入力データを準備
            input_feed = {}
            
            if self.image_input_name:
                input_feed[self.image_input_name] = preprocessed_img
                logger.info(f"Added image input: {self.image_input_name} with shape {preprocessed_img.shape}")
            
            if self.scale_input_name:
                input_feed[self.scale_input_name] = scale_factor
                logger.info(f"Added scale input: {self.scale_input_name} with shape {scale_factor.shape}")
            
            if self.im_shape_input_name:
                input_feed[self.im_shape_input_name] = im_shape
                logger.info(f"Added im_shape input: {self.im_shape_input_name} with shape {im_shape.shape}")
            
            logger.info(f"Input feed keys: {list(input_feed.keys())}")
            
            outputs = self.session.run(None, input_feed)
            logger.info(f"Inference completed, got {len(outputs)} outputs")
            return outputs
        except Exception as e:
            logger.error(f"Inference failed: {e}")
            raise

    @staticmethod
    def _preprocess(
        img_path: str | Path, target_size: tuple[int, int] = (640, 640)
    ) -> tuple[np.ndarray, tuple[int, int], np.ndarray]:
        logger.info(f"Preprocessing image: {img_path}")
        
        # 画像の読み込み
        img = cv2.imread(str(img_path))
        if img is None:
            raise FileNotFoundError(f"Could not load image: {img_path}")

        ori_h, ori_w = img.shape[:2]
        logger.info(f"Original image size: {ori_w}x{ori_h}")
        logger.info(f"Target size: {target_size[0]}x{target_size[1]}")

        # BGR to RGB
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        # リサイズ (Paddingなしの単純リサイズ例)
        img = cv2.resize(img, target_size)

        # Scale factor (h, w)
        scale_h = target_size[1] / ori_h
        scale_w = target_size[0] / ori_w
        scale_factor = np.array([scale_h, scale_w], dtype=np.float32).reshape((1, 2))
        logger.info(f"Scale factors: width={scale_w:.4f}, height={scale_h:.4f}")

        # 正規化 (PaddleOCRの標準的な設定)
        img = img.astype(np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        img = (img - mean) / std

        # HWC to CHW & Batch dimension
        img = img.transpose(2, 0, 1)
        img = np.expand_dims(img, axis=0).astype(np.float32)
        
        logger.info(f"Preprocessed tensor shape: {img.shape}")

        return img, (ori_h, ori_w), scale_factor

    def _postprocess(
        self,
        outputs: list,
        ori_shape: tuple[int, int],
        target_size: tuple[int, int] = (640, 640),
        threshold: float = 0.5,
    ) -> list[dict]:
        """
        outputs[0]: 检测框情報 (N, 6) -> [class_id, score, xmin, ymin, xmax, ymax]
        """
        logger.info(f"Postprocessing with threshold: {threshold}")
        
        predictions = outputs[0]
        ori_h, ori_w = ori_shape
        scale_h, scale_w = ori_h / target_size[1], ori_w / target_size[0]
        
        logger.info(f"Raw predictions shape: {predictions.shape}")
        logger.info(f"Coordinate scale factors: width={scale_w:.4f}, height={scale_h:.4f}")

        results = []
        filtered_count = 0
        
        for res in predictions:
            class_id, score, xmin, ymin, xmax, ymax = res

            if score < threshold:
                filtered_count += 1
                continue

            # 座標を元のサイズに復元
            box = [
                int(xmin * scale_w),
                int(ymin * scale_h),
                int(xmax * scale_w),
                int(ymax * scale_h),
            ]

            results.append({"class_id": int(class_id), "score": float(score), "bbox": box})

        logger.info(f"Filtered out {filtered_count} predictions below threshold {threshold}")
        logger.info(f"Final results: {len(results)} layout elements")
        
        # クラス別統計をログ出力
        class_counts = {}
        for result in results:
            class_id = result["class_id"]
            class_name = self.LABELS[class_id] if class_id < len(self.LABELS) else f"Unknown({class_id})"
            class_counts[class_name] = class_counts.get(class_name, 0) + 1
        
        logger.info("Detection summary by class:")
        for class_name, count in sorted(class_counts.items()):
            logger.info(f"  {class_name}: {count} elements")

        return results

    # ラベルマップ (PP-DocLayoutの一般的なクラス)
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

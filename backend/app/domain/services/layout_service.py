"""
レイアウト解析サービス
PP-DocLayout-L を使用したONNX推論による図表・数式検出
"""

import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import onnxruntime as ort
from pydantic import BaseModel

from app.logger import logger


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

    def __init__(self, model_path: str | None = None):
        """
        Parameters
        ----------
        model_path : str | None
            ONNXモデルファイルのパス。Noneの場合はデフォルトパスを使用
        """
        if model_path is None:
            # デフォルトモデルパス（開発環境用）
            model_path = os.getenv(
                "LAYOUT_MODEL_PATH", 
                "inference-service/models/paddle2onnx/PP-DocLayout-L_infer.onnx"
            )
            # 絶対パスに変換
            if not os.path.isabs(model_path):
                # プロジェクトルートからの相対パス（backend/app/domain/services から ../../../../ で戻る）
                current_dir = Path(__file__).parent  # services
                project_root = current_dir.parent.parent.parent.parent  # paperterrace root
                model_path = str(project_root / model_path)
        
        self.model_path = model_path
        self.session = None
        self.image_input_name = None
        self.scale_input_name = None
        self.im_shape_input_name = None
        
        self._initialize_model()

    def _initialize_model(self):
        """モデルを初期化"""
        logger.info(f"Initializing LayoutAnalysisService...")
        logger.info(f"Model path: {self.model_path}")
        
        # モデルファイルの存在確認
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Model file not found: {self.model_path}")
        
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
        
        logger.info(f"ONNX session config - intra_op_threads: {cpu_count}, inter_op_threads: 1")

        # 推論セッションの初期化
        self.session = ort.InferenceSession(
            self.model_path, 
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
        
        # 入力名を特定
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
            self.image_input_name = inputs[0].name
            logger.warning(f"Could not find image input, using first input: {self.image_input_name}")
        
        logger.info(f"ONNX Runtime providers: {self.session.get_providers()}")
        logger.info("LayoutAnalysisService initialization completed")

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
        logger.info("Starting layout analysis...")
        start_time = time.time()
        
        img, ori_shape, scale_factor = self._preprocess(image_path)
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
        
        # LayoutItemオブジェクトに変換
        layout_items = []
        for result in results:
            bbox = BBox.from_list(result["bbox"])
            class_id = result["class_id"]
            class_name = self.LABELS[class_id] if class_id < len(self.LABELS) else f"Unknown({class_id})"
            
            layout_items.append(LayoutItem(
                bbox=bbox,
                class_name=class_name,
                score=result["score"]
            ))
        
        return layout_items

    def _preprocess(
        self, img_path: str | Path, target_size: tuple[int, int] = (640, 640)
    ) -> tuple[np.ndarray, tuple[int, int], np.ndarray]:
        """画像前処理"""
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

        # リサイズ
        img = cv2.resize(img, target_size)

        # Scale factor (h, w)
        scale_h = target_size[1] / ori_h
        scale_w = target_size[0] / ori_w
        scale_factor = np.array([scale_h, scale_w], dtype=np.float32).reshape((1, 2))
        logger.info(f"Scale factors: width={scale_w:.4f}, height={scale_h:.4f}")

        # 正規化 (PaddleOCRの標準設定)
        img = img.astype(np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        img = (img - mean) / std

        # HWC to CHW & Batch dimension
        img = img.transpose(2, 0, 1)
        img = np.expand_dims(img, axis=0).astype(np.float32)
        
        logger.info(f"Preprocessed tensor shape: {img.shape}")

        return img, (ori_h, ori_w), scale_factor

    def _inference(self, preprocessed_img: np.ndarray, scale_factor: np.ndarray, im_shape: np.ndarray) -> list:
        """ONNX推論実行"""
        logger.info("Running ONNX inference...")

        try:
            # 入力データを準備
            input_feed = {}
            
            if self.image_input_name:
                input_feed[self.image_input_name] = preprocessed_img
                logger.debug(f"Added image input: {self.image_input_name} with shape {preprocessed_img.shape}")
            
            if self.scale_input_name:
                input_feed[self.scale_input_name] = scale_factor
                logger.debug(f"Added scale input: {self.scale_input_name} with shape {scale_factor.shape}")
            
            if self.im_shape_input_name:
                input_feed[self.im_shape_input_name] = im_shape
                logger.debug(f"Added im_shape input: {self.im_shape_input_name} with shape {im_shape.shape}")
            
            outputs = self.session.run(None, input_feed)
            logger.info(f"Inference completed, got {len(outputs)} outputs")
            return outputs
        except Exception as e:
            logger.error(f"Inference failed: {e}")
            raise

    def _postprocess(
        self,
        outputs: list,
        ori_shape: tuple[int, int],
        target_size: tuple[int, int] = (640, 640),
        threshold: float = 0.5,
    ) -> list[dict[str, Any]]:
        """後処理：座標変換とフィルタリング"""
        logger.info(f"Postprocessing with threshold: {threshold}")
        
        predictions = outputs[0]
        ori_h, ori_w = ori_shape
        
        logger.info(f"Raw predictions shape: {predictions.shape}")
        logger.info(f"Original image size: {ori_w}x{ori_h}")

        # 有効な予測を抽出
        valid_mask = predictions[:, 1] >= threshold
        valid_predictions = predictions[valid_mask]
        logger.info(f"Valid predictions (score >= {threshold}): {len(valid_predictions)}")
        
        results = []
        
        if len(valid_predictions) > 0:
            # 座標統計をログ出力
            x_coords = list(valid_predictions[:, 2]) + list(valid_predictions[:, 4])
            y_coords = list(valid_predictions[:, 3]) + list(valid_predictions[:, 5])
            logger.info(f"Coordinate range: X=[{min(x_coords):.1f}, {max(x_coords):.1f}], Y=[{min(y_coords):.1f}, {max(y_coords):.1f}]")
            
            # スケールファクターを決定（前処理の逆変換）
            preprocess_scale_x = target_size[0] / ori_w
            preprocess_scale_y = target_size[1] / ori_h
            scale_x = preprocess_scale_x
            scale_y = preprocess_scale_y
            
            logger.info(f"Using scale factors: x={scale_x:.4f}, y={scale_y:.4f}")
            
            for res in valid_predictions:
                class_id, score, xmin, ymin, xmax, ymax = res

                # 座標を元のサイズに復元
                x1 = max(0, min(ori_w, int(xmin * scale_x)))
                y1 = max(0, min(ori_h, int(ymin * scale_y)))
                x2 = max(0, min(ori_w, int(xmax * scale_x)))
                y2 = max(0, min(ori_h, int(ymax * scale_y)))
                
                box = [x1, y1, x2, y2]
                
                # 有効な座標かチェック
                if box[2] > box[0] and box[3] > box[1]:
                    results.append({
                        "class_id": int(class_id), 
                        "score": float(score), 
                        "bbox": box
                    })

        logger.info(f"Final results: {len(results)} layout elements")
        
        # 座標範囲をチェック
        if results:
            all_x1 = [r["bbox"][0] for r in results]
            all_y1 = [r["bbox"][1] for r in results]
            all_x2 = [r["bbox"][2] for r in results]
            all_y2 = [r["bbox"][3] for r in results]
            logger.info(f"Final coordinate ranges: x=[{min(all_x1)}, {max(all_x2)}], y=[{min(all_y1)}, {max(all_y2)}]")
        
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


# シングルトンインスタンス
_layout_service_instance = None


def get_layout_service() -> LayoutAnalysisService:
    """レイアウト解析サービスのシングルトンインスタンスを取得"""
    global _layout_service_instance
    if _layout_service_instance is None:
        _layout_service_instance = LayoutAnalysisService()
    return _layout_service_instance
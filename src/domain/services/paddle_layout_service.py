import os
from typing import Any, Dict, List, Optional

import cv2
import numpy as np
import onnxruntime as ort

from src.logger import logger


class PaddleLayoutService:
    """
    Paddle-layout-mモデルを使用したレイアウト解析サービス。
    ONNX Runtimeを使用してCPU上で高速に推論を行います。
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PaddleLayoutService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.model_path = os.getenv("LAYOUT_MODEL_PATH", "models/layout_m.onnx")
        self.label_map = {
            0: "text",
            1: "title",
            2: "figure",
            3: "figure_caption",
            4: "table",
            5: "table_caption",
            6: "header",
            7: "footer",
            8: "reference",
            9: "equation",
        }

        self.session: Optional[ort.InferenceSession] = None
        if not os.path.exists(self.model_path):
            logger.warning(
                f"Layout model not found at {self.model_path}. Layout detection will be limited."
            )
        else:
            try:
                # 8 vCPUを最大限活用するためのスレッド設定
                opts = ort.SessionOptions()
                opts.intra_op_num_threads = int(os.getenv("ORT_INTRA_THREADS", "4"))
                opts.inter_op_num_threads = int(os.getenv("ORT_INTER_THREADS", "2"))
                opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL

                self.session = ort.InferenceSession(
                    self.model_path, sess_options=opts, providers=["CPUExecutionProvider"]
                )
                self.input_name = self.session.get_inputs()[0].name
                self.output_names = [o.name for o in self.session.get_outputs()]
                self._initialized = True
                logger.info("PaddleLayoutService initialized successfully with ONNX Runtime.")
            except Exception as e:
                logger.error(f"Failed to initialize PaddleLayoutService: {e}")

    def detect_layout(self, image_bytes: bytes) -> List[Dict[str, Any]]:
        """
        画像バイトデータからレイアウトを検出する。
        """
        if not self._initialized or self.session is None:
            return []

        try:
            # 画像の読み込みと前処理
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                return []

            h, w, _ = img.shape
            # Paddle Layoutの標準的な入力サイズ（可変だが一般的に800x800など）
            # ここではシンプルにリサイズして正規化する例を示す
            input_size = 800
            resized_img = cv2.resize(img, (input_size, input_size))
            input_data = resized_img.astype(np.float32) / 255.0
            input_data = np.transpose(input_data, (2, 0, 1))  # HWC -> CHW
            input_data = np.expand_dims(input_data, axis=0)  # NCHW

            # 推論実行
            outputs = self.session.run(self.output_names, {self.input_name: input_data})

            # 後処理（モデルの出力形式に依存するが、一般的な検出モデルの例）
            # 形式: [x1, y1, x2, y2, score, label_id]
            # 実際にはPaddleOCRのONNXモデルの出力仕様に合わせる必要がある
            results = []

            # 仮のパースロジック（実際のモデル出力に合わせて調整が必要）
            # Paddleの検出モデルは大抵 [N, 6] の形式でボックスを返す
            if len(outputs) > 0:
                detections = outputs[0]
                if len(detections.shape) == 3:  # Some models return [1, N, 6]
                    detections = detections[0]

                for det in detections:
                    if len(det) < 6:
                        continue

                    x1, y1, x2, y2, score, label_id = det[:6]
                    if score < 0.5:  # 閾値
                        continue

                    label_name = self.label_map.get(int(label_id), "unknown")

                    # 座標を元の画像サイズに変換
                    results.append(
                        {
                            "bbox": [
                                x1 * w / input_size,
                                y1 * h / input_size,
                                x2 * w / input_size,
                                y2 * h / input_size,
                            ],
                            "label": label_name,
                            "score": float(score),
                        }
                    )

            return results

        except Exception as e:
            logger.error(f"Layout detection error: {e}")
            return []


def get_layout_service():
    return PaddleLayoutService()

"""
レイアウト解析サービス
ONNX Runtime を使用したPaddle-layout-m推論
"""

import asyncio
import logging
import os
from typing import List, Optional, Dict, Any
import numpy as np
import cv2
from pathlib import Path

try:
    import onnxruntime as ort
except ImportError:
    ort = None

logger = logging.getLogger(__name__)


class LayoutAnalysisService:
    """レイアウト解析サービス"""
    
    def __init__(self):
        self.session: Optional[ort.InferenceSession] = None
        self.model_path = os.getenv("LAYOUT_MODEL_PATH", "models/layout_m.onnx")
        self.input_size = (800, 608)  # Paddle-layout-mの入力サイズ
        
        # ONNX Runtime設定
        self.ort_intra_threads = int(os.getenv("ORT_INTRA_THREADS", "4"))
        self.ort_inter_threads = int(os.getenv("ORT_INTER_THREADS", "2"))
        
        # クラスラベル（Paddle-layout-m）
        self.class_labels = {
            0: "text",
            1: "title", 
            2: "list",
            3: "table",
            4: "figure"
        }
    
    async def initialize(self):
        """モデルの初期化"""
        if ort is None:
            raise RuntimeError("ONNX Runtime がインストールされていません")
        
        if not Path(self.model_path).exists():
            raise FileNotFoundError(f"モデルファイルが見つかりません: {self.model_path}")
        
        logger.info(f"レイアウト解析モデルをロード中: {self.model_path}")
        
        # ONNX Runtime セッション設定
        sess_options = ort.SessionOptions()
        sess_options.intra_op_num_threads = self.ort_intra_threads
        sess_options.inter_op_num_threads = self.ort_inter_threads
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        
        # CPUプロバイダー設定
        providers = ['CPUExecutionProvider']
        
        try:
            self.session = ort.InferenceSession(
                self.model_path,
                sess_options=sess_options,
                providers=providers
            )
            logger.info("レイアウト解析モデルのロード完了")
            
        except Exception as e:
            logger.error(f"モデルロードエラー: {e}")
            raise
    
    async def cleanup(self):
        """リソースのクリーンアップ"""
        if self.session:
            self.session = None
            logger.info("レイアウト解析サービスをクリーンアップしました")
    
    def preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """画像の前処理"""
        # リサイズ
        h, w = image.shape[:2]
        target_h, target_w = self.input_size
        
        # アスペクト比を保持してリサイズ
        scale = min(target_w / w, target_h / h)
        new_w, new_h = int(w * scale), int(h * scale)
        
        resized = cv2.resize(image, (new_w, new_h))
        
        # パディング
        padded = np.zeros((target_h, target_w, 3), dtype=np.uint8)
        padded[:new_h, :new_w] = resized
        
        # 正規化 (0-1)
        normalized = padded.astype(np.float32) / 255.0
        
        # CHW形式に変換
        transposed = np.transpose(normalized, (2, 0, 1))
        
        # バッチ次元追加
        batched = np.expand_dims(transposed, axis=0)
        
        return batched, scale
    
    def postprocess_results(self, outputs: List[np.ndarray], scale: float, 
                          original_size: tuple) -> List[Dict[str, Any]]:
        """推論結果の後処理"""
        results = []
        
        # ONNX出力の解析（モデル依存）
        # 通常: [boxes, scores, classes] の形式
        if len(outputs) >= 3:
            boxes = outputs[0]  # [N, 4]
            scores = outputs[1]  # [N]
            classes = outputs[2]  # [N]
            
            # 信頼度フィルタリング
            confidence_threshold = 0.5
            valid_indices = scores > confidence_threshold
            
            valid_boxes = boxes[valid_indices]
            valid_scores = scores[valid_indices]
            valid_classes = classes[valid_indices]
            
            orig_h, orig_w = original_size
            
            for box, score, cls in zip(valid_boxes, valid_scores, valid_classes):
                # 座標をオリジナルサイズにスケール
                x1, y1, x2, y2 = box
                x1 = int(x1 / scale)
                y1 = int(y1 / scale)
                x2 = int(x2 / scale)
                y2 = int(y2 / scale)
                
                # 境界チェック
                x1 = max(0, min(x1, orig_w))
                y1 = max(0, min(y1, orig_h))
                x2 = max(0, min(x2, orig_w))
                y2 = max(0, min(y2, orig_h))
                
                results.append({
                    "bbox": [x1, y1, x2, y2],
                    "confidence": float(score),
                    "class": self.class_labels.get(int(cls), "unknown"),
                    "class_id": int(cls)
                })
        
        return results
    
    async def analyze_page(self, image_path: str) -> List[Dict[str, Any]]:
        """単一ページの解析"""
        if not self.session:
            raise RuntimeError("モデルが初期化されていません")
        
        # 画像読み込み
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"画像を読み込めません: {image_path}")
        
        original_size = image.shape[:2]
        
        # 前処理
        input_data, scale = self.preprocess_image(image)
        
        # 推論実行
        input_name = self.session.get_inputs()[0].name
        outputs = self.session.run(None, {input_name: input_data})
        
        # 後処理
        results = self.postprocess_results(outputs, scale, original_size)
        
        return results
    
    async def analyze_pdf(self, pdf_path: str, pages: Optional[List[int]] = None) -> List[Dict[str, Any]]:
        """PDFの解析（ページ画像が既に存在することを前提）"""
        results = []
        
        # PDF画像ディレクトリの推定
        pdf_name = Path(pdf_path).stem
        image_dir = Path(f"static/paper_images/{pdf_name}")
        
        if not image_dir.exists():
            raise FileNotFoundError(f"PDF画像ディレクトリが見つかりません: {image_dir}")
        
        # ページリストの決定
        if pages is None:
            # 全ページを処理
            page_files = sorted(image_dir.glob("page_*.png"))
            page_numbers = [int(f.stem.split('_')[1]) for f in page_files]
        else:
            page_numbers = pages
        
        # 各ページを並列処理
        tasks = []
        for page_num in page_numbers:
            image_path = image_dir / f"page_{page_num}.png"
            if image_path.exists():
                task = self._analyze_page_with_metadata(str(image_path), page_num)
                tasks.append(task)
        
        if tasks:
            page_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in page_results:
                if isinstance(result, Exception):
                    logger.error(f"ページ解析エラー: {result}")
                else:
                    results.extend(result)
        
        return results
    
    async def _analyze_page_with_metadata(self, image_path: str, page_num: int) -> List[Dict[str, Any]]:
        """ページ解析にメタデータを追加"""
        page_results = await self.analyze_page(image_path)
        
        # ページ番号を追加
        for result in page_results:
            result["page"] = page_num
            result["image_path"] = image_path
        
        return page_results
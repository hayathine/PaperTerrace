from unittest.mock import patch

import numpy as np
from services.layout_detection.layout_service import LayoutAnalysisService


class TestLayoutAnalysisService:
    @patch("services.layout_detection.layout_service.ort.InferenceSession")
    @patch("services.layout_detection.layout_service.os.path.getsize")
    @patch("services.layout_detection.layout_service.os.path.exists")
    def test_initialization(self, mock_exists, mock_getsize, mock_session):
        mock_exists.return_value = True
        mock_getsize.return_value = 10 * 1024 * 1024
        service = LayoutAnalysisService(model_path="dummy.onnx")
        assert service.model_path == "dummy.onnx"
        assert mock_session.called

    def test_apply_nms_empty(self):
        service = LayoutAnalysisService.__new__(LayoutAnalysisService)
        results = []
        filtered = service._apply_nms(results)
        assert filtered == []

    def test_apply_nms_no_overlap(self):
        service = LayoutAnalysisService.__new__(LayoutAnalysisService)
        results = [
            {"class_id": 1, "score": 0.9, "bbox": [0, 0, 10, 10]},
            {"class_id": 1, "score": 0.8, "bbox": [20, 20, 30, 30]},
        ]
        filtered = service._apply_nms(results)
        assert len(filtered) == 2

    def test_apply_nms_with_overlap(self):
        service = LayoutAnalysisService.__new__(LayoutAnalysisService)
        results = [
            {"class_id": 1, "score": 0.9, "bbox": [0, 0, 10, 10]},
            {
                "class_id": 1,
                "score": 0.8,
                "bbox": [2, 2, 12, 12],
            },  # IoU ~ (8*8)/(100+100-64) = 64/136 = 0.47
        ]
        # With IoU threshold 0.5, both should stay
        filtered = service._apply_nms(results, iou_threshold=0.5)
        assert len(filtered) == 2

        # With IoU threshold 0.4, one should be removed
        filtered = service._apply_nms(results, iou_threshold=0.4)
        assert len(filtered) == 1
        assert filtered[0]["score"] == 0.9

    def test_postprocess_basic(self):
        service = LayoutAnalysisService.__new__(LayoutAnalysisService)
        service.LABELS = ["Text", "Title", "Figure", "Table"]

        # Mock outputs: [class_id, score, x1, y1, x2, y2]
        # Assuming model output is in 640x640 canvas
        outputs = [
            np.array(
                [
                    [2, 0.9, 100, 100, 200, 200],  # Figure, valid
                    [0, 0.4, 50, 50, 150, 150],  # Text, below threshold
                ]
            )
        ]

        ori_shape = (1000, 1000)
        scale = (640 / 1000, 640 / 1000)  # (0.64, 0.64)
        pad_info = np.array([0, 0])

        results = service._postprocess(
            outputs, ori_shape, threshold=0.5, scale=scale, pad_info=pad_info
        )

        assert len(results) == 1
        assert results[0]["class_id"] == 2
        assert results[0]["score"] == 0.9
        # Coord conversion: (100 - 0) / 0.64 = 156.25 -> 156
        assert results[0]["bbox"] == [156, 156, 312, 312]

    @patch("services.layout_detection.preprocess.cv2")
    @patch("services.layout_detection.layout_service.cv2")
    def test_preprocess_logic(self, mock_cv2_ls, mock_cv2_pre):
        # Create a dummy image (100x200)
        dummy_img = np.zeros((100, 200, 3), dtype=np.uint8)

        # Configure both mocks
        for m in [mock_cv2_ls, mock_cv2_pre]:
            m.imread.return_value = dummy_img
            m.cvtColor.return_value = dummy_img
            m.resize.side_effect = lambda img, size: np.zeros(
                (size[1], size[0], 3), dtype=np.uint8
            )
            m.COLOR_BGR2RGB = 4  # Dummy value

        service = LayoutAnalysisService.__new__(LayoutAnalysisService)

        processed_img, ori_shape, scale, pad_info = service._preprocess(
            "dummy.jpg", target_size=(640, 640)
        )

        assert ori_shape == (100, 200)
        # scale = min(640/100, 640/200) = 3.2
        assert scale == (3.2, 3.2)
        # For Center padding:
        # pad_h = (640 - 320) // 2 = 160
        # pad_w = (640 - 640) // 2 = 0
        assert pad_info[0] == 160
        assert pad_info[1] == 0
        assert processed_img.shape == (1, 3, 640, 640)

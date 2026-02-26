import cv2
import numpy as np


class LetterBoxResize:
    def __init__(self, target_size=(640, 640)):
        self.target_size = target_size

    def __call__(self, data):
        img = data["image"]
        h, w = img.shape[:2]
        target_h, target_w = self.target_size
        scale = min(target_h / h, target_w / w)
        new_h, new_w = int(h * scale), int(w * scale)

        resized_img = cv2.resize(img, (new_w, new_h))

        canvas = np.zeros((target_h, target_w, 3), dtype=np.uint8)

        # Top-Left padding (not centered)
        pad_h = 0
        pad_w = 0
        canvas[0:new_h, 0:new_w, :] = resized_img

        data["image"] = canvas
        data["im_shape"] = np.array([new_h, new_w], dtype=np.float32)
        data["scale_factor"] = np.array([scale, scale], dtype=np.float32)
        data["pad_info"] = np.array([pad_h, pad_w], dtype=np.float32)
        return data


class NormalizeImage:
    def __init__(
        self,
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225],
        is_scale=True,
        norm_type="mean_std",
    ):
        self.mean = np.array(mean).reshape((1, 1, 3)).astype("float32")
        self.std = np.array(std).reshape((1, 1, 3)).astype("float32")
        self.is_scale = is_scale
        self.norm_type = norm_type

    def __call__(self, data):
        img = data["image"].astype("float32")
        if self.is_scale:
            img /= 255.0
        if self.norm_type != "none":
            img = (img - self.mean) / self.std
        data["image"] = img
        return data


class Permute:
    def __call__(self, data):
        img = data["image"]
        data["image"] = img.transpose((2, 0, 1))
        return data


def preprocess(img, ops):
    data = {"image": img}
    for op in ops:
        data = op(data)
    return data["image"], data

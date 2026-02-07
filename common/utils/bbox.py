from typing import Any, Dict, List, Sequence, Union

from ..schemas.bbox import BBoxModel


def to_bbox(bbox: Union[Sequence[float], BBoxModel]) -> BBoxModel:
    """Ensure the input is a BBox object."""
    if isinstance(bbox, BBoxModel):
        return bbox
    return BBoxModel.from_list(bbox)


def scale_bbox(
    bbox: Union[Sequence[float], BBoxModel], scale_x: float, scale_y: float
) -> BBoxModel:
    """
    Scale a bounding box by the given factors.
    Returns a new BBox object.
    """
    b = to_bbox(bbox)
    return BBoxModel(
        x_min=b.x_min * scale_x,
        y_min=b.y_min * scale_y,
        x_max=b.x_max * scale_x,
        y_max=b.y_max * scale_y,
    )


def calculate_iou(
    bbox1: Union[Sequence[float], BBoxModel], bbox2: Union[Sequence[float], BBoxModel]
) -> float:
    """
    Calculate Intersection over Union (IoU) of two bboxes.
    """
    b1 = to_bbox(bbox1)
    b2 = to_bbox(bbox2)

    ix0 = max(b1.x_min, b2.x_min)
    iy0 = max(b1.y_min, b2.y_min)
    ix1 = min(b1.x_max, b2.x_max)
    iy1 = min(b1.y_max, b2.y_max)

    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0

    intersection_area = (ix1 - ix0) * (iy1 - iy0)
    union_area = b1.area + b2.area - intersection_area

    if union_area <= 0:
        return 0.0

    return intersection_area / union_area


def is_contained(
    bbox_inner: Union[Sequence[float], BBoxModel],
    bbox_outer: Union[Sequence[float], BBoxModel],
    threshold: float = 0.9,
) -> bool:
    """
    Check if bbox_inner is significantly contained within bbox_outer.
    Useful for filtering redundant detections.
    """
    b_in = to_bbox(bbox_inner)
    b_out = to_bbox(bbox_outer)

    ix0 = max(b_in.x_min, b_out.x_min)
    iy0 = max(b_in.y_min, b_out.y_min)
    ix1 = min(b_in.x_max, b_out.x_max)
    iy1 = min(b_in.y_max, b_out.y_max)

    if ix1 <= ix0 or iy1 <= iy0:
        return False

    intersection_area = (ix1 - ix0) * (iy1 - iy0)
    in_area = b_in.area

    if in_area <= 0:
        return False

    return intersection_area / in_area >= threshold


def get_bbox_from_items(items: Sequence[Dict[str, Any]]) -> BBoxModel:
    """
    Calculate the bounding box enclosing all given items.
    Handles both pdfplumber format (x0, top, x1, bottom) and common (x_min, y_min, x_max, y_max).
    """
    if not items:
        return BBoxModel(x_min=0.0, y_min=0.0, x_max=0.0, y_max=0.0)

    def get_val(item, keys):
        for k in keys:
            if k in item and item[k] is not None:
                return item[k]
        return None

    x0s = [get_val(i, ["x_min", "x0", "left"]) for i in items]
    y0s = [get_val(i, ["y_min", "top", "y0"]) for i in items]
    x1s = [get_val(i, ["x_max", "x1", "right"]) for i in items]
    y1s = [get_val(i, ["y_max", "bottom", "y1"]) for i in items]

    x0 = min(x for x in x0s if x is not None)
    y0 = min(y for y in y0s if y is not None)
    x1 = max(x for x in x1s if x is not None)
    y1 = max(y for y in y1s if y is not None)

    return BBoxModel(x_min=float(x0), y_min=float(y0), x_max=float(x1), y_max=float(y1))


def merge_close_bboxes(
    bboxes: Sequence[Union[Sequence[float], BBoxModel]], threshold: float = 5.0
) -> List[BBoxModel]:
    """
    Merge bboxes that are overlapping or within a certain threshold distance.
    Uses a greedy clustering approach.
    """
    if not bboxes:
        return []

    # Working with BBox objects
    working_bboxes = [to_bbox(b) for b in bboxes]
    merged_results: List[BBoxModel] = []

    while working_bboxes:
        curr = working_bboxes.pop(0)
        has_merged = True

        while has_merged:
            has_merged = False
            for i in range(len(working_bboxes) - 1, -1, -1):
                other = working_bboxes[i]
                # Check for proximity in 2D
                if not (
                    curr.x_min > other.x_max + threshold
                    or curr.x_max < other.x_min - threshold
                    or curr.y_min > other.y_max + threshold
                    or curr.y_max < other.y_min - threshold
                ):
                    # Merge
                    curr = BBoxModel(
                        x_min=min(curr.x_min, other.x_min),
                        y_min=min(curr.y_min, other.y_min),
                        x_max=max(curr.x_max, other.x_max),
                        y_max=max(curr.y_max, other.y_max),
                    )
                    working_bboxes.pop(i)
                    has_merged = True

        merged_results.append(curr)

    return merged_results


def sanitize_bboxes(
    bboxes: Sequence[Union[Sequence[float], BBoxModel]], min_size: float = 5.0
) -> List[BBoxModel]:
    """
    Filters out bboxes that are too small and merges overlaps.
    """
    merged = merge_close_bboxes(bboxes)
    return [b for b in merged if b.width > min_size and b.height > min_size]

"""YOLO-based person detection module.

This module provides real-time person detection using YOLOv8.
"""

from dataclasses import dataclass
from typing import List, Tuple
import logging
import numpy as np
from ultralytics import YOLO

logger = logging.getLogger(__name__)


@dataclass
class Detection:
    """Represents a detected person.

    Attributes:
        bbox: Bounding box as (x1, y1, x2, y2) in pixels
        confidence: Detection confidence score (0.0 to 1.0)
        class_id: Class ID (should be 0 for person in COCO)
    """
    bbox: Tuple[float, float, float, float]
    confidence: float
    class_id: int


class PersonDetector:
    """YOLO-based person detector for real-time detection."""

    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        confidence_threshold: float = 0.5,
        nms_threshold: float = 0.4
    ):
        """Initialize the person detector.

        Args:
            model_path: Path to YOLO model weights
            confidence_threshold: Minimum confidence for detections
            nms_threshold: IoU threshold for non-maximum suppression
        """
        self.model = YOLO(model_path)
        self.confidence_threshold = confidence_threshold
        self.nms_threshold = nms_threshold
        self.person_class_id = 0  # COCO dataset person class

        logger.info(
            f"PersonDetector initialized: model={model_path}, "
            f"conf_thresh={confidence_threshold}, nms_thresh={nms_threshold}"
        )

    def detect(self, frame: np.ndarray) -> List[Detection]:
        """Detect persons in a camera frame.

        Args:
            frame: Input image as numpy array (H, W, 3) in BGR format

        Returns:
            List of Detection objects for detected persons
        """
        if frame is None or frame.size == 0:
            logger.warning("Empty frame received")
            return []

        # Run YOLO inference
        results = self.model(
            frame,
            conf=self.confidence_threshold,
            iou=self.nms_threshold,
            verbose=False
        )

        detections = []

        # Process results
        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue

            for box in boxes:
                class_id = int(box.cls[0])

                # Filter for person class only
                if class_id != self.person_class_id:
                    continue

                confidence = float(box.conf[0])

                # Additional confidence check (YOLO should filter, but double-check)
                if confidence < self.confidence_threshold:
                    continue

                # Get bounding box coordinates
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()

                detection = Detection(
                    bbox=(float(x1), float(y1), float(x2), float(y2)),
                    confidence=confidence,
                    class_id=class_id
                )
                detections.append(detection)

        logger.debug(f"Detected {len(detections)} persons in frame")
        return detections

    def detect_batch(self, frames: List[np.ndarray]) -> List[List[Detection]]:
        """Detect persons in multiple frames (batch processing).

        Args:
            frames: List of input images

        Returns:
            List of detection lists, one per frame
        """
        if not frames:
            return []

        # Run batch inference
        results = self.model(
            frames,
            conf=self.confidence_threshold,
            iou=self.nms_threshold,
            verbose=False
        )

        all_detections = []

        for result in results:
            frame_detections = []
            boxes = result.boxes

            if boxes is not None:
                for box in boxes:
                    class_id = int(box.cls[0])

                    if class_id != self.person_class_id:
                        continue

                    confidence = float(box.conf[0])
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()

                    detection = Detection(
                        bbox=(float(x1), float(y1), float(x2), float(y2)),
                        confidence=confidence,
                        class_id=class_id
                    )
                    frame_detections.append(detection)

            all_detections.append(frame_detections)

        return all_detections

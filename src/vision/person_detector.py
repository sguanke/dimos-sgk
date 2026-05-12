"""YOLO-based person detection module."""

import logging
from dataclasses import dataclass
from typing import List, Optional

import cv2
import numpy as np
from ultralytics import YOLO

logger = logging.getLogger(__name__)


@dataclass
class Detection:
    """Represents a detected person bounding box."""

    bbox: tuple[float, float, float, float]  # (x1, y1, x2, y2)
    confidence: float
    class_id: int
    class_name: str


class PersonDetector:
    """Real-time person detection using YOLOv8."""

    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        confidence_threshold: float = 0.5,
        nms_threshold: float = 0.4,
    ):
        """Initialize person detector.

        Args:
            model_path: Path to YOLO model weights
            confidence_threshold: Minimum confidence for detections
            nms_threshold: Non-maximum suppression threshold
        """
        self.model = YOLO(model_path)
        self.confidence_threshold = confidence_threshold
        self.nms_threshold = nms_threshold
        self.person_class_id = 0  # COCO dataset person class

        logger.info(
            f"PersonDetector initialized: model={model_path}, "
            f"conf={confidence_threshold}, nms={nms_threshold}"
        )

    def detect(self, frame: np.ndarray) -> List[Detection]:
        """Detect persons in a frame.

        Args:
            frame: Input image (BGR format, 1920x1080)

        Returns:
            List of detected person bounding boxes with confidence scores
        """
        if frame is None or frame.size == 0:
            logger.warning("Empty frame received")
            return []

        results = self.model(
            frame,
            conf=self.confidence_threshold,
            iou=self.nms_threshold,
            classes=[self.person_class_id],
            verbose=False,
        )

        detections = self._parse_results(results)

        logger.debug(f"Detected {len(detections)} persons")
        return detections

    def _parse_results(self, results) -> List[Detection]:
        """Parse YOLO results into Detection objects.

        Args:
            results: YOLO detection results

        Returns:
            List of Detection objects
        """
        detections = []

        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue

            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                confidence = float(box.conf[0].cpu().numpy())
                class_id = int(box.cls[0].cpu().numpy())

                if confidence >= self.confidence_threshold:
                    detection = Detection(
                        bbox=(float(x1), float(y1), float(x2), float(y2)),
                        confidence=confidence,
                        class_id=class_id,
                        class_name="person",
                    )
                    detections.append(detection)

        return detections

    def visualize(
        self,
        frame: np.ndarray,
        detections: List[Detection],
    ) -> np.ndarray:
        """Draw detection bounding boxes on frame.

        Args:
            frame: Input image
            detections: List of detections to visualize

        Returns:
            Frame with drawn bounding boxes
        """
        vis_frame = frame.copy()

        for det in detections:
            x1, y1, x2, y2 = det.bbox
            cv2.rectangle(
                vis_frame,
                (int(x1), int(y1)),
                (int(x2), int(y2)),
                (0, 255, 0),
                2,
            )

            label = f"{det.class_name}: {det.confidence:.2f}"
            cv2.putText(
                vis_frame,
                label,
                (int(x1), int(y1) - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                2,
            )

        return vis_frame

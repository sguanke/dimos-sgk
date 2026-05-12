"""Unit tests for person_detector module."""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock

from src.vision.person_detector import PersonDetector, Detection


@pytest.fixture
def mock_yolo_model():
    """Create mock YOLO model."""
    with patch('src.vision.person_detector.YOLO') as mock:
        model = Mock()
        mock.return_value = model
        yield model


@pytest.fixture
def detector(mock_yolo_model):
    """Create PersonDetector instance with mocked YOLO."""
    return PersonDetector(
        model_path="yolov8n.pt",
        confidence_threshold=0.5,
        nms_threshold=0.4
    )


class TestPersonDetector:
    """Test PersonDetector class."""

    def test_initialization(self, detector):
        """Test detector initialization."""
        assert detector.confidence_threshold == 0.5
        assert detector.nms_threshold == 0.4
        assert detector.person_class_id == 0

    def test_detect_empty_frame(self, detector, mock_yolo_model):
        """Test detection with empty frame."""
        mock_yolo_model.return_value = []

        frame = None
        detections = detector.detect(frame)

        assert detections == []

    def test_detect_zero_size_frame(self, detector, mock_yolo_model):
        """Test detection with zero-size frame."""
        mock_yolo_model.return_value = []

        frame = np.array([])
        detections = detector.detect(frame)

        assert detections == []

    def test_detect_valid_frame_no_detections(self, detector, mock_yolo_model):
        """Test detection with valid frame but no persons detected."""
        mock_result = Mock()
        mock_result.boxes = None
        mock_yolo_model.return_value = [mock_result]

        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        detections = detector.detect(frame)

        assert detections == []

    def test_detect_valid_frame_with_detections(self, detector, mock_yolo_model):
        """Test detection with valid frame and person detections."""
        mock_box = Mock()
        mock_box.xyxy = [Mock()]
        mock_box.xyxy[0].cpu.return_value.numpy.return_value = np.array([100, 200, 300, 400])
        mock_box.conf = [Mock()]
        mock_box.conf[0].cpu.return_value.numpy.return_value = 0.85
        mock_box.cls = [Mock()]
        mock_box.cls[0].cpu.return_value.numpy.return_value = 0

        mock_result = Mock()
        mock_result.boxes = [mock_box]
        mock_yolo_model.return_value = [mock_result]

        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        detections = detector.detect(frame)

        assert len(detections) == 1
        assert detections[0].bbox == (100.0, 200.0, 300.0, 400.0)
        assert detections[0].confidence == 0.85
        assert detections[0].class_id == 0
        assert detections[0].class_name == "person"

    def test_detect_multiple_persons(self, detector, mock_yolo_model):
        """Test detection with multiple persons."""
        mock_boxes = []
        for i in range(3):
            mock_box = Mock()
            mock_box.xyxy = [Mock()]
            mock_box.xyxy[0].cpu.return_value.numpy.return_value = np.array([100*i, 200*i, 300*i, 400*i])
            mock_box.conf = [Mock()]
            mock_box.conf[0].cpu.return_value.numpy.return_value = 0.7 + i * 0.1
            mock_box.cls = [Mock()]
            mock_box.cls[0].cpu.return_value.numpy.return_value = 0
            mock_boxes.append(mock_box)

        mock_result = Mock()
        mock_result.boxes = mock_boxes
        mock_yolo_model.return_value = [mock_result]

        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        detections = detector.detect(frame)

        assert len(detections) == 3

    def test_detect_low_confidence_filtered(self, detector, mock_yolo_model):
        """Test that low confidence detections are filtered."""
        mock_box = Mock()
        mock_box.xyxy = [Mock()]
        mock_box.xyxy[0].cpu.return_value.numpy.return_value = np.array([100, 200, 300, 400])
        mock_box.conf = [Mock()]
        mock_box.conf[0].cpu.return_value.numpy.return_value = 0.3  # Below threshold
        mock_box.cls = [Mock()]
        mock_box.cls[0].cpu.return_value.numpy.return_value = 0

        mock_result = Mock()
        mock_result.boxes = [mock_box]
        mock_yolo_model.return_value = [mock_result]

        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        detections = detector.detect(frame)

        assert len(detections) == 0

    def test_visualize_empty_detections(self, detector):
        """Test visualization with no detections."""
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        detections = []

        vis_frame = detector.visualize(frame, detections)

        assert vis_frame.shape == frame.shape
        assert np.array_equal(vis_frame, frame)

    def test_visualize_with_detections(self, detector):
        """Test visualization with detections."""
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        detections = [
            Detection(
                bbox=(100.0, 200.0, 300.0, 400.0),
                confidence=0.85,
                class_id=0,
                class_name="person"
            )
        ]

        vis_frame = detector.visualize(frame, detections)

        assert vis_frame.shape == frame.shape
        assert not np.array_equal(vis_frame, frame)

    def test_parse_results_empty(self, detector):
        """Test parsing empty results."""
        results = []
        detections = detector._parse_results(results)
        assert detections == []

    def test_detection_dataclass(self):
        """Test Detection dataclass."""
        det = Detection(
            bbox=(10.0, 20.0, 30.0, 40.0),
            confidence=0.9,
            class_id=0,
            class_name="person"
        )

        assert det.bbox == (10.0, 20.0, 30.0, 40.0)
        assert det.confidence == 0.9
        assert det.class_id == 0
        assert det.class_name == "person"

"""Unit tests for person_detector module.

Tests the YOLO-based person detection functionality.
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from src.vision.person_detector import PersonDetector, Detection


@pytest.fixture
def mock_yolo_model():
    """Create a mock YOLO model."""
    with patch('src.vision.person_detector.YOLO') as mock:
        yield mock


@pytest.fixture
def detector(mock_yolo_model):
    """Create a PersonDetector instance with mocked YOLO."""
    return PersonDetector(
        model_path="yolov8n.pt",
        confidence_threshold=0.5,
        nms_threshold=0.4
    )


class TestDetection:
    """Test Detection dataclass."""

    def test_detection_creation(self):
        """Test creating a Detection object."""
        det = Detection(
            bbox=(100.0, 200.0, 300.0, 400.0),
            confidence=0.85,
            class_id=0
        )
        assert det.bbox == (100.0, 200.0, 300.0, 400.0)
        assert det.confidence == 0.85
        assert det.class_id == 0


class TestPersonDetector:
    """Test PersonDetector class."""

    def test_initialization(self, detector, mock_yolo_model):
        """Test detector initialization."""
        assert detector.confidence_threshold == 0.5
        assert detector.nms_threshold == 0.4
        assert detector.person_class_id == 0
        mock_yolo_model.assert_called_once_with("yolov8n.pt")

    def test_detect_empty_frame(self, detector):
        """Test detection with empty frame."""
        empty_frame = None
        detections = detector.detect(empty_frame)
        assert detections == []

    def test_detect_zero_size_frame(self, detector):
        """Test detection with zero-size frame."""
        zero_frame = np.array([])
        detections = detector.detect(zero_frame)
        assert detections == []

    def test_detect_single_person(self, detector):
        """Test detection with single person in frame."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        # Mock YOLO result
        mock_box = Mock()
        mock_box.cls = [0]  # person class
        mock_box.conf = [0.85]
        mock_box.xyxy = [Mock()]
        mock_box.xyxy[0].cpu().numpy.return_value = np.array([100, 150, 300, 450])

        mock_boxes = Mock()
        mock_boxes.__iter__ = Mock(return_value=iter([mock_box]))

        mock_result = Mock()
        mock_result.boxes = mock_boxes

        detector.model.return_value = [mock_result]

        detections = detector.detect(frame)

        assert len(detections) == 1
        assert detections[0].bbox == (100.0, 150.0, 300.0, 450.0)
        assert detections[0].confidence == 0.85
        assert detections[0].class_id == 0

    def test_detect_multiple_people(self, detector):
        """Test detection with multiple people in frame."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        # Mock two person detections
        mock_box1 = Mock()
        mock_box1.cls = [0]
        mock_box1.conf = [0.90]
        mock_box1.xyxy = [Mock()]
        mock_box1.xyxy[0].cpu().numpy.return_value = np.array([50, 100, 200, 400])

        mock_box2 = Mock()
        mock_box2.cls = [0]
        mock_box2.conf = [0.75]
        mock_box2.xyxy = [Mock()]
        mock_box2.xyxy[0].cpu().numpy.return_value = np.array([400, 100, 550, 400])

        mock_boxes = Mock()
        mock_boxes.__iter__ = Mock(return_value=iter([mock_box1, mock_box2]))

        mock_result = Mock()
        mock_result.boxes = mock_boxes

        detector.model.return_value = [mock_result]

        detections = detector.detect(frame)

        assert len(detections) == 2
        assert detections[0].confidence == 0.90
        assert detections[1].confidence == 0.75

    def test_detect_filters_non_person_classes(self, detector):
        """Test that non-person classes are filtered out."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        # Mock detections with different classes
        mock_box_person = Mock()
        mock_box_person.cls = [0]  # person
        mock_box_person.conf = [0.85]
        mock_box_person.xyxy = [Mock()]
        mock_box_person.xyxy[0].cpu().numpy.return_value = np.array([100, 150, 300, 450])

        mock_box_car = Mock()
        mock_box_car.cls = [2]  # car (not person)
        mock_box_car.conf = [0.95]
        mock_box_car.xyxy = [Mock()]
        mock_box_car.xyxy[0].cpu().numpy.return_value = np.array([400, 200, 600, 400])

        mock_boxes = Mock()
        mock_boxes.__iter__ = Mock(return_value=iter([mock_box_person, mock_box_car]))

        mock_result = Mock()
        mock_result.boxes = mock_boxes

        detector.model.return_value = [mock_result]

        detections = detector.detect(frame)

        # Only person should be detected
        assert len(detections) == 1
        assert detections[0].class_id == 0

    def test_detect_filters_low_confidence(self, detector):
        """Test that low confidence detections are filtered."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        # Mock detection with low confidence
        mock_box = Mock()
        mock_box.cls = [0]
        mock_box.conf = [0.3]  # Below threshold of 0.5
        mock_box.xyxy = [Mock()]
        mock_box.xyxy[0].cpu().numpy.return_value = np.array([100, 150, 300, 450])

        mock_boxes = Mock()
        mock_boxes.__iter__ = Mock(return_value=iter([mock_box]))

        mock_result = Mock()
        mock_result.boxes = mock_boxes

        detector.model.return_value = [mock_result]

        detections = detector.detect(frame)

        # Low confidence detection should be filtered
        assert len(detections) == 0

    def test_detect_no_boxes_in_result(self, detector):
        """Test detection when YOLO returns no boxes."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        mock_result = Mock()
        mock_result.boxes = None

        detector.model.return_value = [mock_result]

        detections = detector.detect(frame)

        assert len(detections) == 0

    def test_detect_batch_empty_list(self, detector):
        """Test batch detection with empty list."""
        detections = detector.detect_batch([])
        assert detections == []

    def test_detect_batch_multiple_frames(self, detector):
        """Test batch detection with multiple frames."""
        frames = [
            np.zeros((480, 640, 3), dtype=np.uint8),
            np.zeros((480, 640, 3), dtype=np.uint8)
        ]

        # Mock results for two frames
        mock_box1 = Mock()
        mock_box1.cls = [0]
        mock_box1.conf = [0.85]
        mock_box1.xyxy = [Mock()]
        mock_box1.xyxy[0].cpu().numpy.return_value = np.array([100, 150, 300, 450])

        mock_boxes1 = Mock()
        mock_boxes1.__iter__ = Mock(return_value=iter([mock_box1]))

        mock_result1 = Mock()
        mock_result1.boxes = mock_boxes1

        mock_result2 = Mock()
        mock_result2.boxes = None

        detector.model.return_value = [mock_result1, mock_result2]

        all_detections = detector.detect_batch(frames)

        assert len(all_detections) == 2
        assert len(all_detections[0]) == 1  # First frame has 1 detection
        assert len(all_detections[1]) == 0  # Second frame has no detections

    def test_detect_calls_yolo_with_correct_params(self, detector):
        """Test that YOLO is called with correct parameters."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        mock_result = Mock()
        mock_result.boxes = None
        detector.model.return_value = [mock_result]

        detector.detect(frame)

        detector.model.assert_called_once_with(
            frame,
            conf=0.5,
            iou=0.4,
            verbose=False
        )

    def test_detect_with_valid_frame_shape(self, detector):
        """Test detection with various valid frame shapes."""
        # Test different resolutions
        for height, width in [(480, 640), (720, 1280), (1080, 1920)]:
            frame = np.zeros((height, width, 3), dtype=np.uint8)

            mock_result = Mock()
            mock_result.boxes = None
            detector.model.return_value = [mock_result]

            detections = detector.detect(frame)
            assert isinstance(detections, list)

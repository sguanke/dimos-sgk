"""Unit tests for person_tracker module."""

import pytest
import numpy as np
from unittest.mock import Mock, patch

from src.vision.person_tracker import PersonTracker, Track
from src.vision.person_detector import Detection


@pytest.fixture
def mock_deepsort():
    """Create mock DeepSORT tracker."""
    with patch('src.vision.person_tracker.DeepSort') as mock:
        tracker = Mock()
        mock.return_value = tracker
        yield tracker


@pytest.fixture
def tracker(mock_deepsort):
    """Create PersonTracker instance with mocked DeepSORT."""
    return PersonTracker(max_age=30, n_init=3, max_iou_distance=0.7)


class TestPersonTracker:
    """Test PersonTracker class."""

    def test_initialization(self, tracker):
        """Test tracker initialization."""
        assert tracker.max_age == 30
        assert tracker.n_init == 3
        assert tracker.prev_tracks == {}

    def test_update_empty_frame(self, tracker, mock_deepsort):
        """Test update with empty frame."""
        mock_deepsort.update_tracks.return_value = []

        frame = None
        detections = []
        tracks = tracker.update(frame, detections)

        assert tracks == []

    def test_update_zero_size_frame(self, tracker, mock_deepsort):
        """Test update with zero-size frame."""
        mock_deepsort.update_tracks.return_value = []

        frame = np.array([])
        detections = []
        tracks = tracker.update(frame, detections)

        assert tracks == []

    def test_update_no_detections(self, tracker, mock_deepsort):
        """Test update with no detections."""
        mock_deepsort.update_tracks.return_value = []

        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        detections = []
        tracks = tracker.update(frame, detections)

        assert tracks == []

    def test_update_with_detections(self, tracker, mock_deepsort):
        """Test update with valid detections."""
        mock_track = Mock()
        mock_track.is_confirmed.return_value = True
        mock_track.track_id = 1
        mock_track.to_ltrb.return_value = [100, 200, 300, 400]
        mock_track.get_det_conf.return_value = 0.85
        mock_track.age = 5
        mock_track.time_since_update = 0

        mock_deepsort.update_tracks.return_value = [mock_track]

        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        detections = [
            Detection(
                bbox=(100.0, 200.0, 300.0, 400.0),
                confidence=0.85,
                class_id=0,
                class_name="person"
            )
        ]

        tracks = tracker.update(frame, detections)

        assert len(tracks) == 1
        assert tracks[0].track_id == 1
        assert tracks[0].bbox == (100.0, 200.0, 300.0, 400.0)
        assert tracks[0].confidence == 0.85

    def test_update_unconfirmed_tracks_filtered(self, tracker, mock_deepsort):
        """Test that unconfirmed tracks are filtered out."""
        mock_track = Mock()
        mock_track.is_confirmed.return_value = False

        mock_deepsort.update_tracks.return_value = [mock_track]

        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        detections = []
        tracks = tracker.update(frame, detections)

        assert len(tracks) == 0

    def test_velocity_computation(self, tracker, mock_deepsort):
        """Test velocity computation between frames."""
        mock_track = Mock()
        mock_track.is_confirmed.return_value = True
        mock_track.track_id = 1
        mock_track.to_ltrb.return_value = [100, 200, 300, 400]
        mock_track.get_det_conf.return_value = 0.85
        mock_track.age = 5
        mock_track.time_since_update = 0

        mock_deepsort.update_tracks.return_value = [mock_track]

        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        detections = [Detection((100.0, 200.0, 300.0, 400.0), 0.85, 0, "person")]

        tracks1 = tracker.update(frame, detections)
        assert tracks1[0].velocity == (0.0, 0.0)

        mock_track.to_ltrb.return_value = [120, 220, 320, 420]
        tracks2 = tracker.update(frame, detections)

        assert tracks2[0].velocity == (20.0, 20.0)

    def test_convert_detections(self, tracker):
        """Test detection format conversion."""
        detections = [
            Detection(
                bbox=(100.0, 200.0, 300.0, 400.0),
                confidence=0.85,
                class_id=0,
                class_name="person"
            )
        ]

        raw_detections = tracker._convert_detections(detections)

        assert len(raw_detections) == 1
        assert raw_detections[0][0] == [100.0, 200.0, 200.0, 200.0]
        assert raw_detections[0][1] == 0.85
        assert raw_detections[0][2] == "person"

    def test_get_track_by_id_exists(self, tracker, mock_deepsort):
        """Test getting track by ID when it exists."""
        mock_track = Mock()
        mock_track.is_confirmed.return_value = True
        mock_track.track_id = 1
        mock_track.to_ltrb.return_value = [100, 200, 300, 400]
        mock_track.get_det_conf.return_value = 0.85
        mock_track.age = 5
        mock_track.time_since_update = 0

        mock_deepsort.update_tracks.return_value = [mock_track]

        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        detections = [Detection((100.0, 200.0, 300.0, 400.0), 0.85, 0, "person")]
        tracker.update(frame, detections)

        track = tracker.get_track_by_id(1)
        assert track is not None
        assert track.track_id == 1

    def test_get_track_by_id_not_exists(self, tracker):
        """Test getting track by ID when it doesn't exist."""
        track = tracker.get_track_by_id(999)
        assert track is None

    def test_track_dataclass(self):
        """Test Track dataclass."""
        track = Track(
            track_id=1,
            bbox=(100.0, 200.0, 300.0, 400.0),
            confidence=0.85,
            velocity=(5.0, 10.0),
            age=10,
            time_since_update=0
        )

        assert track.track_id == 1
        assert track.bbox == (100.0, 200.0, 300.0, 400.0)
        assert track.confidence == 0.85
        assert track.velocity == (5.0, 10.0)
        assert track.age == 10

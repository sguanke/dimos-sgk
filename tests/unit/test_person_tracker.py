"""Unit tests for person_tracker module.

Tests the DeepSORT-based multi-person tracking functionality.
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from src.vision.person_tracker import PersonTracker, Track
from src.vision.person_detector import Detection


@pytest.fixture
def mock_deepsort():
    """Create a mock DeepSORT tracker."""
    with patch('src.vision.person_tracker.DeepSort') as mock:
        yield mock


@pytest.fixture
def tracker(mock_deepsort):
    """Create a PersonTracker instance with mocked DeepSORT."""
    return PersonTracker(max_age=30, n_init=3, max_iou_distance=0.7)


class TestTrack:
    """Test Track dataclass."""

    def test_track_creation(self):
        """Test creating a Track object."""
        track = Track(
            track_id=1,
            bbox=(100.0, 200.0, 300.0, 400.0),
            confidence=0.85,
            velocity=(5.0, 2.0),
            age=10,
            time_since_update=0
        )
        assert track.track_id == 1
        assert track.bbox == (100.0, 200.0, 300.0, 400.0)
        assert track.confidence == 0.85
        assert track.velocity == (5.0, 2.0)
        assert track.age == 10
        assert track.time_since_update == 0


class TestPersonTracker:
    """Test PersonTracker class."""

    def test_initialization(self, tracker, mock_deepsort):
        """Test tracker initialization."""
        assert tracker.max_age == 30
        assert tracker.n_init == 3
        mock_deepsort.assert_called_once()

    def test_update_empty_frame(self, tracker):
        """Test update with empty frame."""
        detections = [Detection(bbox=(100, 200, 300, 400), confidence=0.85, class_id=0)]
        empty_frame = None

        tracks = tracker.update(detections, empty_frame)

        assert tracks == []

    def test_update_zero_size_frame(self, tracker):
        """Test update with zero-size frame."""
        detections = [Detection(bbox=(100, 200, 300, 400), confidence=0.85, class_id=0)]
        zero_frame = np.array([])

        tracks = tracker.update(detections, zero_frame)

        assert tracks == []

    def test_update_with_detections(self, tracker):
        """Test update with valid detections."""
        detections = [
            Detection(bbox=(100, 150, 300, 450), confidence=0.85, class_id=0),
            Detection(bbox=(400, 150, 600, 450), confidence=0.90, class_id=0)
        ]
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        # Mock DeepSORT track
        mock_track = Mock()
        mock_track.is_confirmed.return_value = True
        mock_track.track_id = 1
        mock_track.to_ltrb.return_value = [100, 150, 300, 450]
        mock_track.det_conf = 0.85
        mock_track.age = 5
        mock_track.time_since_update = 0
        mock_track.mean = [200, 300, 1.5, 300, 5.0, 2.0, 0, 0]

        tracker.tracker.update_tracks.return_value = [mock_track]

        tracks = tracker.update(detections, frame)

        assert len(tracks) == 1
        assert tracks[0].track_id == 1
        assert tracks[0].confidence == 0.85

    def test_update_filters_unconfirmed_tracks(self, tracker):
        """Test that unconfirmed tracks are filtered out."""
        detections = [Detection(bbox=(100, 150, 300, 450), confidence=0.85, class_id=0)]
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        # Mock unconfirmed track
        mock_track = Mock()
        mock_track.is_confirmed.return_value = False

        tracker.tracker.update_tracks.return_value = [mock_track]

        tracks = tracker.update(detections, frame)

        assert len(tracks) == 0

    def test_estimate_velocity_with_mean(self, tracker):
        """Test velocity estimation from track mean."""
        mock_track = Mock()
        mock_track.mean = [200, 300, 1.5, 300, 5.0, 2.0, 0, 0]

        velocity = tracker._estimate_velocity(mock_track)

        assert velocity == (5.0, 2.0)

    def test_estimate_velocity_without_mean(self, tracker):
        """Test velocity estimation when mean is not available."""
        mock_track = Mock()
        mock_track.mean = None

        velocity = tracker._estimate_velocity(mock_track)

        assert velocity == (0.0, 0.0)

    def test_estimate_velocity_short_mean(self, tracker):
        """Test velocity estimation with short mean vector."""
        mock_track = Mock()
        mock_track.mean = [200, 300]  # Too short

        velocity = tracker._estimate_velocity(mock_track)

        assert velocity == (0.0, 0.0)

    def test_get_track_by_id_found(self, tracker):
        """Test getting track by ID when it exists."""
        tracks = [
            Track(1, (100, 200, 300, 400), 0.85, (5.0, 2.0), 10, 0),
            Track(2, (400, 200, 600, 400), 0.90, (3.0, 1.0), 8, 0)
        ]

        track = tracker.get_track_by_id(tracks, 2)

        assert track is not None
        assert track.track_id == 2

    def test_get_track_by_id_not_found(self, tracker):
        """Test getting track by ID when it doesn't exist."""
        tracks = [
            Track(1, (100, 200, 300, 400), 0.85, (5.0, 2.0), 10, 0)
        ]

        track = tracker.get_track_by_id(tracks, 99)

        assert track is None

    def test_reset(self, tracker, mock_deepsort):
        """Test resetting tracker."""
        initial_call_count = mock_deepsort.call_count

        tracker.reset()

        # DeepSORT should be recreated
        assert mock_deepsort.call_count > initial_call_count

    def test_detection_format_conversion(self, tracker):
        """Test that detections are converted to DeepSORT format correctly."""
        detections = [
            Detection(bbox=(100, 150, 300, 450), confidence=0.85, class_id=0)
        ]
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        tracker.tracker.update_tracks.return_value = []

        tracker.update(detections, frame)

        # Verify update_tracks was called with correct format
        call_args = tracker.tracker.update_tracks.call_args
        raw_detections = call_args[0][0]

        assert len(raw_detections) == 1
        # Format should be [[x1, y1, w, h], confidence, 'person']
        bbox, conf, label = raw_detections[0]
        assert bbox == [100, 150, 200, 300]  # x1, y1, w, h
        assert conf == 0.85
        assert label == 'person'

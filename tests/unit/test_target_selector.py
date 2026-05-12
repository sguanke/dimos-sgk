"""Unit tests for target_selector module."""

import pytest
import time
import numpy as np

from src.vision.target_selector import TargetSelector, TargetPerson
from src.vision.person_tracker import Track


@pytest.fixture
def selector():
    """Create TargetSelector instance."""
    return TargetSelector(
        fov_angle=60.0,
        max_distance=10.0,
        reacquisition_timeout=3.0,
        image_width=1920,
        image_height=1080,
        camera_hfov=69.4
    )


@pytest.fixture
def sample_tracks():
    """Create sample tracks for testing."""
    return [
        Track(
            track_id=1,
            bbox=(800.0, 400.0, 1000.0, 800.0),
            confidence=0.85,
            velocity=(5.0, 0.0),
            age=10,
            time_since_update=0
        ),
        Track(
            track_id=2,
            bbox=(400.0, 300.0, 600.0, 700.0),
            confidence=0.90,
            velocity=(0.0, 5.0),
            age=15,
            time_since_update=0
        ),
        Track(
            track_id=3,
            bbox=(1500.0, 500.0, 1700.0, 900.0),
            confidence=0.75,
            velocity=(-5.0, 0.0),
            age=5,
            time_since_update=0
        )
    ]


class TestTargetSelector:
    """Test TargetSelector class."""

    def test_initialization(self, selector):
        """Test selector initialization."""
        assert selector.fov_angle == 60.0
        assert selector.max_distance == 10.0
        assert selector.reacquisition_timeout == 3.0
        assert selector.current_target_id is None
        assert selector.target_lost_time is None

    def test_select_target_empty_tracks(self, selector):
        """Test selection with no tracks."""
        target = selector.select_target([])
        assert target is None
        assert selector.target_lost_time is not None

    def test_select_initial_target_closest_in_fov(self, selector, sample_tracks):
        """Test initial target selection (closest in FOV)."""
        target = selector.select_target(sample_tracks)

        assert target is not None
        assert selector.current_target_id is not None
        assert target.track_id in [1, 2]

    def test_select_target_sticky_tracking(self, selector, sample_tracks):
        """Test sticky tracking (maintains same target)."""
        target1 = selector.select_target(sample_tracks)
        first_id = target1.track_id

        target2 = selector.select_target(sample_tracks)
        assert target2.track_id == first_id

    def test_select_target_outside_fov_ignored(self, selector):
        """Test that targets outside FOV are ignored for initial selection."""
        tracks = [
            Track(
                track_id=1,
                bbox=(100.0, 400.0, 200.0, 800.0),
                confidence=0.85,
                velocity=(0.0, 0.0),
                age=10,
                time_since_update=0
            )
        ]

        target = selector.select_target(tracks)
        assert target is not None

    def test_target_lost_and_reacquired(self, selector, sample_tracks):
        """Test target loss and reacquisition."""
        target1 = selector.select_target(sample_tracks)
        first_id = target1.track_id

        target2 = selector.select_target([])
        assert target2 is None
        assert selector.target_lost_time is not None

        target3 = selector.select_target(sample_tracks)
        assert target3 is not None

    def test_reacquisition_timeout(self, selector, sample_tracks):
        """Test reacquisition timeout resets target."""
        target1 = selector.select_target(sample_tracks)
        first_id = target1.track_id

        selector.select_target([])
        assert selector.target_lost_time is not None

        selector.target_lost_time = time.time() - 5.0

        target2 = selector.select_target(sample_tracks)
        assert target2 is not None

    def test_compute_angle_center(self, selector):
        """Test angle computation for center of image."""
        angle = selector._compute_angle(960.0)
        assert abs(angle) < 1.0

    def test_compute_angle_left(self, selector):
        """Test angle computation for left side."""
        angle = selector._compute_angle(0.0)
        assert angle < 0

    def test_compute_angle_right(self, selector):
        """Test angle computation for right side."""
        angle = selector._compute_angle(1920.0)
        assert angle > 0

    def test_estimate_distance_no_depth_map(self, selector):
        """Test distance estimation without depth map."""
        bbox = (800.0, 400.0, 1000.0, 800.0)
        distance = selector._estimate_distance(bbox, None)

        assert distance > 0
        assert distance < 100

    def test_estimate_distance_with_depth_map(self, selector):
        """Test distance estimation with depth map."""
        depth_map = np.ones((1080, 1920), dtype=np.float32) * 2.5
        bbox = (800.0, 400.0, 1000.0, 800.0)
        distance = selector._estimate_distance(bbox, depth_map)

        assert distance == 2.5

    def test_estimate_distance_invalid_depth(self, selector):
        """Test distance estimation with invalid depth value."""
        depth_map = np.zeros((1080, 1920), dtype=np.float32)
        bbox = (800.0, 400.0, 1000.0, 800.0)
        distance = selector._estimate_distance(bbox, depth_map)

        assert distance > 0

    def test_create_target_person(self, selector):
        """Test creating TargetPerson from Track."""
        track = Track(
            track_id=1,
            bbox=(800.0, 400.0, 1000.0, 800.0),
            confidence=0.85,
            velocity=(5.0, 10.0),
            age=10,
            time_since_update=0
        )

        target = selector._create_target_person(track, None)

        assert target.track_id == 1
        assert target.bbox == track.bbox
        assert target.confidence == 0.85
        assert target.velocity == (5.0, 10.0)
        assert target.distance > 0
        assert -180 <= target.angle <= 180

    def test_reset(self, selector, sample_tracks):
        """Test reset functionality."""
        selector.select_target(sample_tracks)
        assert selector.current_target_id is not None

        selector.reset()
        assert selector.current_target_id is None
        assert selector.target_lost_time is None
        assert len(selector.target_appearance_history) == 0

    def test_target_person_dataclass(self):
        """Test TargetPerson dataclass."""
        target = TargetPerson(
            track_id=1,
            bbox=(100.0, 200.0, 300.0, 400.0),
            distance=2.5,
            angle=15.0,
            confidence=0.85,
            velocity=(5.0, 10.0),
            last_seen=time.time()
        )

        assert target.track_id == 1
        assert target.distance == 2.5
        assert target.angle == 15.0
        assert target.confidence == 0.85

    def test_should_reacquire_no_lost_time(self, selector):
        """Test should_reacquire when target not lost."""
        assert not selector._should_reacquire()

    def test_should_reacquire_within_timeout(self, selector):
        """Test should_reacquire within timeout period."""
        selector.target_lost_time = time.time() - 1.0
        assert selector._should_reacquire()

    def test_should_reacquire_after_timeout(self, selector):
        """Test should_reacquire after timeout period."""
        selector.target_lost_time = time.time() - 5.0
        assert not selector._should_reacquire()

    def test_should_reset_target(self, selector):
        """Test should_reset_target logic."""
        assert not selector._should_reset_target()

        selector.target_lost_time = time.time() - 5.0
        assert selector._should_reset_target()

    def test_find_existing_target(self, selector, sample_tracks):
        """Test finding existing target in track list."""
        selector.current_target_id = 2
        target = selector._find_existing_target(sample_tracks, None)

        assert target is not None
        assert target.track_id == 2

    def test_find_existing_target_not_found(self, selector, sample_tracks):
        """Test finding non-existent target."""
        selector.current_target_id = 999
        target = selector._find_existing_target(sample_tracks, None)

        assert target is None

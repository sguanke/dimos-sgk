"""Target person selection and re-acquisition logic."""

import logging
import time
from dataclasses import dataclass
from typing import Optional, List

import numpy as np

from .person_tracker import Track

logger = logging.getLogger(__name__)


@dataclass
class TargetPerson:
    """Represents the selected target person to follow."""

    track_id: int
    bbox: tuple[float, float, float, float]
    distance: float  # Estimated distance in meters
    angle: float  # Angle from robot center in degrees
    confidence: float
    velocity: tuple[float, float]
    last_seen: float  # Timestamp


class TargetSelector:
    """Select and maintain target person for following."""

    def __init__(
        self,
        fov_angle: float = 60.0,
        max_distance: float = 10.0,
        reacquisition_timeout: float = 3.0,
        image_width: int = 1920,
        image_height: int = 1080,
        camera_hfov: float = 69.4,  # Go2 camera horizontal FOV
    ):
        """Initialize target selector.

        Args:
            fov_angle: Field of view angle for initial selection (degrees)
            max_distance: Maximum distance to consider (meters)
            reacquisition_timeout: Time to attempt re-acquisition (seconds)
            image_width: Camera image width in pixels
            image_height: Camera image height in pixels
            camera_hfov: Camera horizontal field of view (degrees)
        """
        self.fov_angle = fov_angle
        self.max_distance = max_distance
        self.reacquisition_timeout = reacquisition_timeout
        self.image_width = image_width
        self.image_height = image_height
        self.camera_hfov = camera_hfov

        self.current_target_id: Optional[int] = None
        self.target_lost_time: Optional[float] = None
        self.target_appearance_history = []

        logger.info(
            f"TargetSelector initialized: fov={fov_angle}°, "
            f"max_dist={max_distance}m, timeout={reacquisition_timeout}s"
        )

    def select_target(
        self,
        tracks: List[Track],
        depth_map: Optional[np.ndarray] = None,
    ) -> Optional[TargetPerson]:
        """Select target person from tracked persons.

        Args:
            tracks: List of tracked persons
            depth_map: Optional depth map for distance estimation

        Returns:
            Selected target person or None if no valid target
        """
        if not tracks:
            self._handle_target_lost()
            return None

        if self.current_target_id is not None:
            target = self._find_existing_target(tracks, depth_map)
            if target is not None:
                self.target_lost_time = None
                return target

        if self._should_reacquire():
            logger.info("Attempting target re-acquisition")
            target = self._reacquire_target(tracks, depth_map)
            if target is not None:
                self.current_target_id = target.track_id
                self.target_lost_time = None
                return target

        if self.current_target_id is None:
            target = self._select_initial_target(tracks, depth_map)
            if target is not None:
                self.current_target_id = target.track_id
                self.target_lost_time = None
                logger.info(f"Selected new target: ID={target.track_id}")
                return target

        self._handle_target_lost()
        return None

    def _find_existing_target(
        self,
        tracks: List[Track],
        depth_map: Optional[np.ndarray],
    ) -> Optional[TargetPerson]:
        """Find current target in track list.

        Args:
            tracks: List of tracked persons
            depth_map: Optional depth map

        Returns:
            Target person if found, None otherwise
        """
        for track in tracks:
            if track.track_id == self.current_target_id:
                return self._create_target_person(track, depth_map)
        return None

    def _select_initial_target(
        self,
        tracks: List[Track],
        depth_map: Optional[np.ndarray],
    ) -> Optional[TargetPerson]:
        """Select initial target (closest person in front).

        Args:
            tracks: List of tracked persons
            depth_map: Optional depth map

        Returns:
            Selected target person or None
        """
        candidates = []

        for track in tracks:
            target = self._create_target_person(track, depth_map)

            if abs(target.angle) <= self.fov_angle / 2:
                if target.distance <= self.max_distance:
                    candidates.append(target)

        if not candidates:
            return None

        candidates.sort(key=lambda t: t.distance)
        return candidates[0]

    def _reacquire_target(
        self,
        tracks: List[Track],
        depth_map: Optional[np.ndarray],
    ) -> Optional[TargetPerson]:
        """Attempt to re-acquire lost target using appearance.

        Args:
            tracks: List of tracked persons
            depth_map: Optional depth map

        Returns:
            Re-acquired target or None
        """
        candidates = []

        for track in tracks:
            target = self._create_target_person(track, depth_map)
            if abs(target.angle) <= self.fov_angle:
                candidates.append(target)

        if not candidates:
            return None

        candidates.sort(key=lambda t: t.distance)
        return candidates[0]

    def _create_target_person(
        self,
        track: Track,
        depth_map: Optional[np.ndarray],
    ) -> TargetPerson:
        """Create TargetPerson from Track.

        Args:
            track: Track object
            depth_map: Optional depth map for distance estimation

        Returns:
            TargetPerson object
        """
        x1, y1, x2, y2 = track.bbox
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2

        angle = self._compute_angle(cx)
        distance = self._estimate_distance(track.bbox, depth_map)

        return TargetPerson(
            track_id=track.track_id,
            bbox=track.bbox,
            distance=distance,
            angle=angle,
            confidence=track.confidence,
            velocity=track.velocity,
            last_seen=time.time(),
        )

    def _compute_angle(self, center_x: float) -> float:
        """Compute angle from robot center to person.

        Args:
            center_x: Person center x-coordinate in pixels

        Returns:
            Angle in degrees (negative = left, positive = right)
        """
        image_center = self.image_width / 2
        pixel_offset = center_x - image_center
        angle = (pixel_offset / self.image_width) * self.camera_hfov
        return angle

    def _estimate_distance(
        self,
        bbox: tuple[float, float, float, float],
        depth_map: Optional[np.ndarray],
    ) -> float:
        """Estimate distance to person.

        Args:
            bbox: Bounding box (x1, y1, x2, y2)
            depth_map: Optional depth map

        Returns:
            Estimated distance in meters
        """
        if depth_map is not None:
            x1, y1, x2, y2 = bbox
            cx = int((x1 + x2) / 2)
            cy = int((y1 + y2) / 2)

            if 0 <= cy < depth_map.shape[0] and 0 <= cx < depth_map.shape[1]:
                distance = depth_map[cy, cx]
                if distance > 0:
                    return float(distance)

        x1, y1, x2, y2 = bbox
        bbox_height = y2 - y1
        avg_person_height = 1.7
        focal_length = 1000.0
        distance = (avg_person_height * focal_length) / bbox_height
        return distance

    def _handle_target_lost(self) -> None:
        """Handle target lost event."""
        if self.target_lost_time is None:
            self.target_lost_time = time.time()
            logger.warning(f"Target lost: ID={self.current_target_id}")

        if self._should_reset_target():
            logger.info("Target re-acquisition timeout, resetting target")
            self.current_target_id = None
            self.target_lost_time = None

    def _should_reacquire(self) -> bool:
        """Check if should attempt target re-acquisition.

        Returns:
            True if should attempt re-acquisition
        """
        if self.target_lost_time is None:
            return False

        elapsed = time.time() - self.target_lost_time
        return elapsed < self.reacquisition_timeout

    def _should_reset_target(self) -> bool:
        """Check if should reset target selection.

        Returns:
            True if should reset target
        """
        if self.target_lost_time is None:
            return False

        elapsed = time.time() - self.target_lost_time
        return elapsed >= self.reacquisition_timeout

    def reset(self) -> None:
        """Reset target selection."""
        self.current_target_id = None
        self.target_lost_time = None
        self.target_appearance_history.clear()
        logger.info("Target selection reset")

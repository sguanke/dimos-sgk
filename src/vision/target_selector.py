"""Target person selection and tracking module.

This module selects and maintains focus on a target person for following.
"""

from dataclasses import dataclass
from typing import Optional, Tuple
import logging
import time
import math

from .person_tracker import Track

logger = logging.getLogger(__name__)


@dataclass
class TargetPerson:
    """Represents the selected target person to follow.

    Attributes:
        track_id: Unique ID of the target track
        bbox: Bounding box as (x1, y1, x2, y2) in pixels
        position: Estimated 3D position as (x, y, distance) in meters
        velocity: Velocity as (vx, vy) in pixels/frame
        confidence: Detection confidence
        last_seen: Timestamp when target was last detected
    """
    track_id: int
    bbox: Tuple[float, float, float, float]
    position: Tuple[float, float, float]
    velocity: Tuple[float, float]
    confidence: float
    last_seen: float


class TargetSelector:
    """Selects and maintains target person for robot following."""

    def __init__(
        self,
        fov_angle: float = 60.0,
        max_distance: float = 10.0,
        reacquisition_timeout: float = 3.0,
        image_width: int = 1920,
        image_height: int = 1080
    ):
        """Initialize the target selector.

        Args:
            fov_angle: Field of view angle in degrees
            max_distance: Maximum distance to consider targets (meters)
            reacquisition_timeout: Time to attempt re-acquisition (seconds)
            image_width: Camera image width in pixels
            image_height: Camera image height in pixels
        """
        self.fov_angle = fov_angle
        self.max_distance = max_distance
        self.reacquisition_timeout = reacquisition_timeout
        self.image_width = image_width
        self.image_height = image_height

        self.current_target: Optional[TargetPerson] = None
        self.target_lost_time: Optional[float] = None

        logger.info(
            f"TargetSelector initialized: fov={fov_angle}°, "
            f"max_dist={max_distance}m, timeout={reacquisition_timeout}s"
        )

    def select_target(self, tracks: list[Track]) -> Optional[TargetPerson]:
        """Select or update target person from tracked persons.

        Args:
            tracks: List of currently tracked persons

        Returns:
            TargetPerson if a target is selected, None otherwise
        """
        current_time = time.time()

        # If we have a current target, try to maintain it (sticky tracking)
        if self.current_target is not None:
            target_track = self._find_track_by_id(
                tracks,
                self.current_target.track_id
            )

            if target_track is not None:
                # Target still tracked, update it
                self.current_target = self._track_to_target(
                    target_track,
                    current_time
                )
                self.target_lost_time = None
                logger.debug(f"Target {self.current_target.track_id} maintained")
                return self.current_target
            else:
                # Target lost, check if within reacquisition timeout
                if self.target_lost_time is None:
                    self.target_lost_time = current_time
                    logger.warning(
                        f"Target {self.current_target.track_id} lost, "
                        f"attempting re-acquisition"
                    )

                time_since_lost = current_time - self.target_lost_time

                if time_since_lost < self.reacquisition_timeout:
                    # Still within timeout, keep current target info
                    logger.debug(
                        f"Target lost for {time_since_lost:.1f}s, "
                        f"waiting for re-acquisition"
                    )
                    return self.current_target
                else:
                    # Timeout exceeded, clear target
                    logger.warning(
                        f"Target {self.current_target.track_id} "
                        f"lost for >{self.reacquisition_timeout}s, clearing"
                    )
                    self.current_target = None
                    self.target_lost_time = None

        # No current target or target lost, select new one
        if not tracks:
            return None

        # Filter tracks: in FOV and within max distance
        valid_tracks = self._filter_valid_tracks(tracks)

        if not valid_tracks:
            logger.debug("No valid tracks in FOV")
            return None

        # Select closest person in front of robot
        closest_track = self._select_closest_track(valid_tracks)

        if closest_track is not None:
            self.current_target = self._track_to_target(
                closest_track,
                current_time
            )
            self.target_lost_time = None
            logger.info(f"New target selected: ID {self.current_target.track_id}")
            return self.current_target

        return None

    def _find_track_by_id(
        self,
        tracks: list[Track],
        track_id: int
    ) -> Optional[Track]:
        """Find a track by its ID."""
        for track in tracks:
            if track.track_id == track_id:
                return track
        return None

    def _filter_valid_tracks(self, tracks: list[Track]) -> list[Track]:
        """Filter tracks that are in FOV and within max distance."""
        valid_tracks = []

        for track in tracks:
            # Check if track is in FOV (centered in image)
            if not self._is_in_fov(track):
                continue

            # Estimate distance (rough approximation from bbox height)
            distance = self._estimate_distance(track)
            if distance > self.max_distance:
                continue

            valid_tracks.append(track)

        return valid_tracks

    def _is_in_fov(self, track: Track) -> bool:
        """Check if track is within field of view."""
        x1, y1, x2, y2 = track.bbox
        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2

        # Calculate angle from image center
        image_center_x = self.image_width / 2
        dx = center_x - image_center_x

        # Approximate horizontal FOV angle
        angle = math.degrees(math.atan2(dx, image_center_x))

        return abs(angle) <= self.fov_angle / 2

    def _estimate_distance(self, track: Track) -> float:
        """Estimate distance to person from bounding box height.

        Uses rough approximation: distance ∝ 1 / bbox_height
        Assumes average person height of 1.7m.
        """
        x1, y1, x2, y2 = track.bbox
        bbox_height = y2 - y1

        if bbox_height <= 0:
            return self.max_distance

        # Rough calibration: person at 2m has bbox height ~400 pixels
        # distance = (1.7 * focal_length) / bbox_height
        # Simplified: distance ≈ 800 / bbox_height
        distance = 800.0 / bbox_height

        return min(distance, self.max_distance)

    def _select_closest_track(self, tracks: list[Track]) -> Optional[Track]:
        """Select the closest track from valid tracks."""
        if not tracks:
            return None

        closest_track = None
        min_distance = float('inf')

        for track in tracks:
            distance = self._estimate_distance(track)
            if distance < min_distance:
                min_distance = distance
                closest_track = track

        return closest_track

    def _track_to_target(
        self,
        track: Track,
        timestamp: float
    ) -> TargetPerson:
        """Convert Track to TargetPerson."""
        x1, y1, x2, y2 = track.bbox
        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2

        distance = self._estimate_distance(track)

        # Convert pixel position to approximate world position
        # Assume camera is centered on robot
        image_center_x = self.image_width / 2
        dx_pixels = center_x - image_center_x

        # Rough conversion: lateral offset in meters
        x_world = (dx_pixels / self.image_width) * distance * 2

        return TargetPerson(
            track_id=track.track_id,
            bbox=track.bbox,
            position=(x_world, 0.0, distance),
            velocity=track.velocity,
            confidence=track.confidence,
            last_seen=timestamp
        )

    def reset(self):
        """Reset target selection state."""
        self.current_target = None
        self.target_lost_time = None
        logger.info("Target selector reset")

    def get_current_target(self) -> Optional[TargetPerson]:
        """Get the current target person."""
        return self.current_target

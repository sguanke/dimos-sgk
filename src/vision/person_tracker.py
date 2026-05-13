"""DeepSORT-based person tracking module.

This module provides multi-person tracking with unique ID assignment.
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional
import logging
import numpy as np
from deep_sort_realtime.deepsort_tracker import DeepSort

from .person_detector import Detection

logger = logging.getLogger(__name__)


@dataclass
class Track:
    """Represents a tracked person.

    Attributes:
        track_id: Unique identifier for this track
        bbox: Bounding box as (x1, y1, x2, y2) in pixels
        confidence: Detection confidence score
        velocity: Estimated velocity as (vx, vy) in pixels/frame
        age: Number of frames this track has existed
        time_since_update: Frames since last detection match
    """
    track_id: int
    bbox: Tuple[float, float, float, float]
    confidence: float
    velocity: Tuple[float, float]
    age: int
    time_since_update: int


class PersonTracker:
    """DeepSORT-based multi-person tracker."""

    def __init__(
        self,
        max_age: int = 30,
        n_init: int = 3,
        max_iou_distance: float = 0.7,
        embedder: str = "mobilenet"
    ):
        """Initialize the person tracker.

        Args:
            max_age: Maximum frames to keep track without detection
            n_init: Number of consecutive detections before track is confirmed
            max_iou_distance: Maximum IoU distance for matching
            embedder: Feature extractor model for re-identification
        """
        self.tracker = DeepSort(
            max_age=max_age,
            n_init=n_init,
            max_iou_distance=max_iou_distance,
            embedder=embedder,
            embedder_gpu=True
        )
        self.max_age = max_age
        self.n_init = n_init

        logger.info(
            f"PersonTracker initialized: max_age={max_age}, "
            f"n_init={n_init}, max_iou_distance={max_iou_distance}"
        )

    def update(
        self,
        detections: List[Detection],
        frame: np.ndarray
    ) -> List[Track]:
        """Update tracker with new detections.

        Args:
            detections: List of Detection objects from person detector
            frame: Current frame for appearance feature extraction

        Returns:
            List of Track objects for confirmed tracks
        """
        if frame is None or frame.size == 0:
            logger.warning("Empty frame received for tracking")
            return []

        # Convert detections to DeepSORT format
        # Format: [[x1, y1, w, h, confidence], ...]
        raw_detections = []
        for det in detections:
            x1, y1, x2, y2 = det.bbox
            w = x2 - x1
            h = y2 - y1
            raw_detections.append(([x1, y1, w, h], det.confidence, 'person'))

        # Update tracker
        tracked_objects = self.tracker.update_tracks(
            raw_detections,
            frame=frame
        )

        # Convert to Track objects
        tracks = []
        for track in tracked_objects:
            if not track.is_confirmed():
                continue

            # Get bounding box
            ltrb = track.to_ltrb()
            x1, y1, x2, y2 = ltrb

            # Estimate velocity from track history
            velocity = self._estimate_velocity(track)

            track_obj = Track(
                track_id=track.track_id,
                bbox=(float(x1), float(y1), float(x2), float(y2)),
                confidence=float(track.det_conf) if track.det_conf else 0.0,
                velocity=velocity,
                age=track.age,
                time_since_update=track.time_since_update
            )
            tracks.append(track_obj)

        logger.debug(f"Tracking {len(tracks)} confirmed persons")
        return tracks

    def _estimate_velocity(
        self,
        track
    ) -> Tuple[float, float]:
        """Estimate velocity from track history.

        Args:
            track: DeepSORT track object

        Returns:
            Velocity as (vx, vy) in pixels/frame
        """
        # Get track state (position and velocity from Kalman filter)
        if hasattr(track, 'mean') and track.mean is not None:
            # DeepSORT uses Kalman filter with state [x, y, a, h, vx, vy, va, vh]
            # where (x, y) is center, a is aspect ratio, h is height
            if len(track.mean) >= 6:
                vx = float(track.mean[4])
                vy = float(track.mean[5])
                return (vx, vy)

        return (0.0, 0.0)

    def get_track_by_id(
        self,
        tracks: List[Track],
        track_id: int
    ) -> Optional[Track]:
        """Get a specific track by ID.

        Args:
            tracks: List of current tracks
            track_id: ID of track to find

        Returns:
            Track object if found, None otherwise
        """
        for track in tracks:
            if track.track_id == track_id:
                return track
        return None

    def reset(self):
        """Reset tracker state (clear all tracks)."""
        self.tracker = DeepSort(
            max_age=self.max_age,
            n_init=self.n_init,
            embedder="mobilenet",
            embedder_gpu=True
        )
        logger.info("Tracker reset")

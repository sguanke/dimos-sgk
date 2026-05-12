"""DeepSORT-based multi-person tracking module."""

import logging
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
from deep_sort_realtime.deepsort_tracker import DeepSort

from .person_detector import Detection

logger = logging.getLogger(__name__)


@dataclass
class Track:
    """Represents a tracked person with unique ID."""

    track_id: int
    bbox: tuple[float, float, float, float]  # (x1, y1, x2, y2)
    confidence: float
    velocity: tuple[float, float] = (0.0, 0.0)  # (vx, vy) in pixels/frame
    age: int = 0  # Number of frames since first detection
    time_since_update: int = 0  # Frames since last detection
    appearance_features: Optional[np.ndarray] = None


class PersonTracker:
    """Robust multi-person tracking using DeepSORT."""

    def __init__(
        self,
        max_age: int = 30,
        n_init: int = 3,
        max_iou_distance: float = 0.7,
    ):
        """Initialize person tracker.

        Args:
            max_age: Maximum frames to keep track without detection
            n_init: Number of consecutive detections before track is confirmed
            max_iou_distance: Maximum IOU distance for matching
        """
        self.tracker = DeepSort(
            max_age=max_age,
            n_init=n_init,
            max_iou_distance=max_iou_distance,
            embedder="mobilenet",
            embedder_gpu=True,
        )
        self.max_age = max_age
        self.n_init = n_init
        self.prev_tracks = {}  # track_id -> Track

        logger.info(
            f"PersonTracker initialized: max_age={max_age}, "
            f"n_init={n_init}, max_iou={max_iou_distance}"
        )

    def update(
        self,
        frame: np.ndarray,
        detections: List[Detection],
    ) -> List[Track]:
        """Update tracker with new detections.

        Args:
            frame: Current frame for appearance feature extraction
            detections: List of person detections from current frame

        Returns:
            List of tracked persons with IDs and velocities
        """
        if frame is None or frame.size == 0:
            logger.warning("Empty frame received")
            return []

        raw_detections = self._convert_detections(detections)

        tracker_outputs = self.tracker.update_tracks(
            raw_detections,
            frame=frame,
        )

        tracks = self._parse_tracks(tracker_outputs)

        self._compute_velocities(tracks)

        self.prev_tracks = {track.track_id: track for track in tracks}

        logger.debug(f"Tracking {len(tracks)} persons")
        return tracks

    def _convert_detections(
        self,
        detections: List[Detection],
    ) -> List[tuple]:
        """Convert Detection objects to DeepSORT format.

        Args:
            detections: List of Detection objects

        Returns:
            List of tuples ([x1, y1, w, h], confidence, class_name)
        """
        raw_detections = []

        for det in detections:
            x1, y1, x2, y2 = det.bbox
            w = x2 - x1
            h = y2 - y1
            raw_detections.append(
                ([x1, y1, w, h], det.confidence, det.class_name)
            )

        return raw_detections

    def _parse_tracks(self, tracker_outputs) -> List[Track]:
        """Parse DeepSORT outputs into Track objects.

        Args:
            tracker_outputs: DeepSORT track outputs

        Returns:
            List of Track objects
        """
        tracks = []

        for track in tracker_outputs:
            if not track.is_confirmed():
                continue

            track_id = track.track_id
            ltrb = track.to_ltrb()
            x1, y1, x2, y2 = ltrb

            track_obj = Track(
                track_id=track_id,
                bbox=(float(x1), float(y1), float(x2), float(y2)),
                confidence=float(track.get_det_conf() or 0.0),
                age=track.age,
                time_since_update=track.time_since_update,
            )

            tracks.append(track_obj)

        return tracks

    def _compute_velocities(self, tracks: List[Track]) -> None:
        """Compute velocity for each track based on previous frame.

        Args:
            tracks: List of current tracks (modified in-place)
        """
        for track in tracks:
            if track.track_id in self.prev_tracks:
                prev_track = self.prev_tracks[track.track_id]

                prev_cx = (prev_track.bbox[0] + prev_track.bbox[2]) / 2
                prev_cy = (prev_track.bbox[1] + prev_track.bbox[3]) / 2

                curr_cx = (track.bbox[0] + track.bbox[2]) / 2
                curr_cy = (track.bbox[1] + track.bbox[3]) / 2

                vx = curr_cx - prev_cx
                vy = curr_cy - prev_cy

                track.velocity = (vx, vy)

    def get_track_by_id(self, track_id: int) -> Optional[Track]:
        """Get track by ID.

        Args:
            track_id: Track ID to retrieve

        Returns:
            Track object if found, None otherwise
        """
        return self.prev_tracks.get(track_id)

"""Mock camera for testing.

This module provides mock camera implementations for testing vision modules
without requiring actual camera hardware.
"""

import numpy as np
from typing import Optional, Tuple


class MockCamera:
    """Mock camera for testing."""

    def __init__(
        self,
        width: int = 1920,
        height: int = 1080,
        fps: int = 30
    ):
        """Initialize mock camera.

        Args:
            width: Frame width in pixels
            height: Frame height in pixels
            fps: Frames per second
        """
        self.width = width
        self.height = height
        self.fps = fps
        self.is_open = False
        self.frame_count = 0

    def open(self) -> bool:
        """Open camera connection.

        Returns:
            True if successful
        """
        self.is_open = True
        return True

    def close(self) -> None:
        """Close camera connection."""
        self.is_open = False

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Read a frame from camera.

        Returns:
            Tuple of (success, frame)
        """
        if not self.is_open:
            return False, None

        # Generate a blank frame
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        self.frame_count += 1
        return True, frame

    def get_frame_with_person(
        self,
        person_bbox: Tuple[int, int, int, int]
    ) -> np.ndarray:
        """Generate a frame with a person bounding box drawn.

        Args:
            person_bbox: Bounding box as (x1, y1, x2, y2)

        Returns:
            Frame with person region highlighted
        """
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        x1, y1, x2, y2 = person_bbox

        # Draw a white rectangle for the person
        frame[y1:y2, x1:x2] = 255

        return frame

    def get_frame_with_multiple_people(
        self,
        person_bboxes: list
    ) -> np.ndarray:
        """Generate a frame with multiple people.

        Args:
            person_bboxes: List of bounding boxes

        Returns:
            Frame with multiple person regions
        """
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)

        for i, bbox in enumerate(person_bboxes):
            x1, y1, x2, y2 = bbox
            # Use different intensities for different people
            intensity = 255 - (i * 50)
            frame[y1:y2, x1:x2] = intensity

        return frame

    def get_empty_frame(self) -> np.ndarray:
        """Generate an empty frame with no people.

        Returns:
            Empty frame
        """
        return np.zeros((self.height, self.width, 3), dtype=np.uint8)

    def get_noisy_frame(self) -> np.ndarray:
        """Generate a noisy frame (random pixels).

        Returns:
            Noisy frame
        """
        return np.random.randint(0, 256, (self.height, self.width, 3), dtype=np.uint8)

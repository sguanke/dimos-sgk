"""Mock camera for testing."""

import numpy as np


class MockCamera:
    """Mock camera that generates test frames."""

    def __init__(self, width: int = 1920, height: int = 1080):
        self.width = width
        self.height = height
        self.frame_count = 0

    def read(self) -> tuple[bool, np.ndarray]:
        """Generate mock frame."""
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        self.frame_count += 1
        return True, frame

    def release(self) -> None:
        """Mock release."""
        pass

    def create_frame_with_person(
        self, x: int, y: int, width: int, height: int
    ) -> np.ndarray:
        """Create frame with person bounding box area."""
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        frame[y:y+height, x:x+width] = 128
        return frame

    def create_test_image(self, pattern: str = "blank") -> np.ndarray:
        """Create test image with specified pattern."""
        if pattern == "blank":
            return np.zeros((self.height, self.width, 3), dtype=np.uint8)
        elif pattern == "noise":
            return np.random.randint(0, 255, (self.height, self.width, 3), dtype=np.uint8)
        elif pattern == "gradient":
            frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
            for i in range(self.height):
                frame[i, :] = int(255 * i / self.height)
            return frame
        else:
            return np.zeros((self.height, self.width, 3), dtype=np.uint8)

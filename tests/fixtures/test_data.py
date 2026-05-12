"""Sample test data for integration tests.

Provides sample images, video sequences, and sensor data for testing.
"""

import numpy as np
from typing import List, Tuple


def create_test_frame(width: int = 640, height: int = 480) -> np.ndarray:
    """Create a blank test frame.

    Args:
        width: Frame width
        height: Frame height

    Returns:
        Blank BGR image
    """
    return np.zeros((height, width, 3), dtype=np.uint8)


def create_frame_with_person(
    width: int = 640,
    height: int = 480,
    person_bbox: Tuple[int, int, int, int] = (200, 150, 300, 350)
) -> np.ndarray:
    """Create test frame with a person rectangle.

    Args:
        width: Frame width
        height: Frame height
        person_bbox: Person bounding box (x1, y1, x2, y2)

    Returns:
        BGR image with person rectangle
    """
    frame = create_test_frame(width, height)
    x1, y1, x2, y2 = person_bbox
    # Draw white rectangle for person
    frame[y1:y2, x1:x2] = 255
    return frame


def create_video_sequence(
    num_frames: int = 30,
    person_trajectory: List[Tuple[int, int, int, int]] = None
) -> List[np.ndarray]:
    """Create a sequence of test frames simulating person movement.

    Args:
        num_frames: Number of frames to generate
        person_trajectory: List of bounding boxes for each frame

    Returns:
        List of BGR images
    """
    if person_trajectory is None:
        # Default: person walking from left to right
        person_trajectory = []
        for i in range(num_frames):
            x_offset = int(i * 10)
            person_trajectory.append((100 + x_offset, 150, 200 + x_offset, 350))

    frames = []
    for bbox in person_trajectory[:num_frames]:
        frame = create_frame_with_person(person_bbox=bbox)
        frames.append(frame)

    return frames


def create_multiple_people_frame(
    width: int = 640,
    height: int = 480,
    people_bboxes: List[Tuple[int, int, int, int]] = None
) -> np.ndarray:
    """Create test frame with multiple people.

    Args:
        width: Frame width
        height: Frame height
        people_bboxes: List of bounding boxes for each person

    Returns:
        BGR image with multiple person rectangles
    """
    if people_bboxes is None:
        people_bboxes = [
            (100, 150, 200, 350),
            (300, 150, 400, 350),
            (500, 150, 600, 350),
        ]

    frame = create_test_frame(width, height)
    for bbox in people_bboxes:
        x1, y1, x2, y2 = bbox
        # Draw white rectangle for each person
        frame[y1:y2, x1:x2] = 255

    return frame


def create_mock_imu_data(
    num_samples: int = 100,
    stationary: bool = True
) -> List[dict]:
    """Create mock IMU data sequence.

    Args:
        num_samples: Number of IMU samples
        stationary: If True, robot is stationary; otherwise add motion

    Returns:
        List of IMU data dictionaries
    """
    imu_data = []
    for i in range(num_samples):
        if stationary:
            data = {
                'accel_x': 0.0,
                'accel_y': 0.0,
                'accel_z': 9.81,
                'gyro_x': 0.0,
                'gyro_y': 0.0,
                'gyro_z': 0.0,
                'timestamp': i * 0.02  # 50Hz
            }
        else:
            # Add some motion
            data = {
                'accel_x': np.sin(i * 0.1) * 0.5,
                'accel_y': np.cos(i * 0.1) * 0.3,
                'accel_z': 9.81 + np.random.normal(0, 0.1),
                'gyro_x': np.random.normal(0, 0.05),
                'gyro_y': np.random.normal(0, 0.05),
                'gyro_z': np.sin(i * 0.05) * 0.2,
                'timestamp': i * 0.02
            }
        imu_data.append(data)

    return imu_data


def create_mock_encoder_data(
    num_samples: int = 100,
    stationary: bool = True
) -> List[dict]:
    """Create mock wheel encoder data sequence.

    Args:
        num_samples: Number of encoder samples
        stationary: If True, robot is stationary; otherwise add motion

    Returns:
        List of encoder data dictionaries
    """
    encoder_data = []
    left_ticks = 0
    right_ticks = 0

    for i in range(num_samples):
        if not stationary:
            # Simulate forward motion
            left_ticks += 10
            right_ticks += 10

        data = {
            'left_ticks': left_ticks,
            'right_ticks': right_ticks,
            'timestamp': i * 0.02  # 50Hz
        }
        encoder_data.append(data)

    return encoder_data


def create_test_obstacle_map(
    width: int = 100,
    height: int = 100,
    obstacles: List[Tuple[int, int, int, int]] = None
) -> np.ndarray:
    """Create test occupancy grid with obstacles.

    Args:
        width: Grid width (cells)
        height: Grid height (cells)
        obstacles: List of obstacle rectangles (x1, y1, x2, y2)

    Returns:
        Occupancy grid (0=free, 1=occupied, -1=unknown)
    """
    grid = np.zeros((height, width), dtype=np.int8)

    if obstacles is None:
        # Default: add some obstacles
        obstacles = [
            (20, 20, 30, 30),
            (60, 40, 70, 50),
            (40, 70, 50, 80),
        ]

    for obs in obstacles:
        x1, y1, x2, y2 = obs
        grid[y1:y2, x1:x2] = 1  # Mark as occupied

    return grid


# Sample test scenarios
SCENARIO_PERSON_WALKS_STRAIGHT = {
    'name': 'Person walks straight',
    'description': 'Person walks straight ahead at constant speed',
    'num_frames': 30,
    'trajectory': [(200 + i*5, 150, 300 + i*5, 350) for i in range(30)],
    'expected_behavior': 'Robot follows with forward motion'
}

SCENARIO_PERSON_TURNS_LEFT = {
    'name': 'Person turns left',
    'description': 'Person turns left while walking',
    'num_frames': 30,
    'trajectory': [(200 - i*3, 150, 300 - i*3, 350) for i in range(30)],
    'expected_behavior': 'Robot turns left to follow'
}

SCENARIO_PERSON_TURNS_RIGHT = {
    'name': 'Person turns right',
    'description': 'Person turns right while walking',
    'num_frames': 30,
    'trajectory': [(200 + i*3, 150, 300 + i*3, 350) for i in range(30)],
    'expected_behavior': 'Robot turns right to follow'
}

SCENARIO_PERSON_STOPS = {
    'name': 'Person stops',
    'description': 'Person stops suddenly',
    'num_frames': 30,
    'trajectory': [(250, 150, 350, 350)] * 30,  # Same position
    'expected_behavior': 'Robot stops and maintains distance'
}

SCENARIO_MULTIPLE_PEOPLE = {
    'name': 'Multiple people',
    'description': 'Multiple people in scene, track closest',
    'num_frames': 30,
    'people_trajectories': [
        [(200, 150, 300, 350)] * 30,  # Person 1 (closest)
        [(400, 150, 500, 350)] * 30,  # Person 2
        [(50, 150, 150, 350)] * 30,   # Person 3
    ],
    'expected_behavior': 'Robot follows closest person (Person 1)'
}

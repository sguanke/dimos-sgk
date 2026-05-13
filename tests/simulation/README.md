# Simulation Tests

This directory contains end-to-end simulation tests for the Go2 person following system.

## Test Modules

### test_following_scenarios.py
Tests person following behavior in various movement scenarios:
- **Straight line following**: Person walking at different speeds (0.5, 1.0, 1.5 m/s)
- **Curved path following**: Gentle curves and circular paths
- **Dynamic behavior**: Person stops, changes direction, accelerates/decelerates

**Key Metrics**:
- Following distance error (target: < 0.3m)
- Tracking success rate (target: > 95%)
- Response time to person movements (target: < 0.5s)

### test_obstacle_avoidance.py
Tests navigation around obstacles while following:
- **Single obstacle avoidance**: Obstacles in direct path, left side, right side
- **Multiple obstacles**: Corridors, cluttered environments
- **Combined following and avoidance**: Following person around obstacles

**Key Metrics**:
- Collision avoidance success rate (target: 100%)
- Minimum clearance maintained (target: > 0.3m)
- Path efficiency while avoiding obstacles

### test_edge_cases.py
Tests edge cases and failure scenarios:
- **Multiple people**: Target selection, sticky tracking, switching targets
- **Target loss**: FOV exit, occlusion, reacquisition
- **Low light conditions**: Low confidence detections, intermittent detections
- **Battery scenarios**: Warning thresholds, critical shutdown
- **Emergency scenarios**: Close approach, collision detection
- **System health**: CPU usage, frame rate degradation, network latency
- **Robustness**: Rapid switching, noisy detections, extreme speeds

## Running Tests

### Run all simulation tests
```bash
pytest tests/simulation/ -v
```

### Run specific test module
```bash
pytest tests/simulation/test_following_scenarios.py -v
pytest tests/simulation/test_obstacle_avoidance.py -v
pytest tests/simulation/test_edge_cases.py -v
```

### Run specific test class
```bash
pytest tests/simulation/test_following_scenarios.py::TestFollowingStraightLine -v
```

### Run with coverage
```bash
pytest tests/simulation/ --cov=src --cov-report=html
```

## Test Fixtures

The `fixtures/` directory contains test data:
- **Video sequences**: Recorded camera footage for vision testing
- **Test maps**: Synthetic obstacle maps for navigation testing
- **Sensor data**: Mock IMU, odometry, and LiDAR data

### Adding Test Data

To add new test data:
1. Place video files in `fixtures/videos/`
2. Place map files in `fixtures/maps/`
3. Place sensor data in `fixtures/sensor_data/`

Example:
```python
import cv2
from pathlib import Path

# Load test video
video_path = Path(__file__).parent / "fixtures" / "videos" / "person_walking.mp4"
cap = cv2.VideoCapture(str(video_path))
```

## Simulation Environment

The simulation tests use mock hardware components:
- **MockGo2SDK**: Simulates Go2 robot control
- **MockCamera**: Generates synthetic camera frames
- **MockMessageBus**: Simulates dimos message passing

### Example Usage

```python
from tests.mocks.mock_go2 import MockGo2SDK
from tests.mocks.mock_camera import MockCamera

def test_example():
    robot = MockGo2SDK()
    robot.connect()
    
    camera = MockCamera()
    camera.open()
    
    # Generate frame with person
    frame = camera.get_frame_with_person((100, 100, 200, 400))
    
    # Control robot
    robot.set_velocity(0.5, 0.0, 0.0)
    
    # Check command history
    history = robot.get_command_history()
    assert len(history) > 0
```

## Performance Targets

### Following Accuracy
- Distance error: < 0.3m (95% of time)
- Target distance: 2.0m ± 0.3m
- Tracking success rate: > 95%

### Safety
- Collision avoidance: 100% success
- Emergency stop response: < 100ms
- Minimum clearance: > 0.3m

### Responsiveness
- Response to person movement: < 0.5s
- Control loop frequency: 50Hz
- Vision processing: > 20 FPS

## Test Data Generation

### Generate Synthetic Trajectories

```python
import numpy as np

# Straight line trajectory
positions = [(0.5 * t, 2.0) for t in np.linspace(0, 10, 50)]
timestamps = list(np.linspace(0, 10, 50))

# Circular trajectory
radius = 3.0
angles = np.linspace(0, 2 * np.pi, 100)
positions = [(radius * np.cos(a), radius * np.sin(a)) for a in angles]
```

### Generate Obstacle Maps

```python
from tests.simulation.test_obstacle_avoidance import ObstacleEnvironment

env = ObstacleEnvironment()
env.add_obstacle(2.5, 2.0, 0.5)  # x, y, radius
grid = env.create_occupancy_grid()
```

## Debugging Tests

### Enable Visualization

Set `--visualize` flag to see camera feed with detections:
```bash
pytest tests/simulation/ -v -s --visualize
```

### Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Inspect Command History

```python
def test_debug_commands(sim_env):
    # ... run simulation ...
    
    history = sim_env.robot.get_command_history()
    for i, cmd in enumerate(history):
        print(f"Step {i}: linear_x={cmd['linear_x']:.2f}, "
              f"angular_z={cmd['angular_z']:.2f}")
```

## Known Limitations

- Simulation uses simplified physics (no dynamics, no slip)
- Mock camera generates synthetic frames (not realistic images)
- No actual YOLO/DeepSORT processing in mocks
- Obstacle detection is perfect (no sensor noise)
- Network latency is not simulated

## Future Enhancements

- [ ] Add recorded video playback for vision testing
- [ ] Integrate with Go2 simulator (if available)
- [ ] Add physics simulation (friction, dynamics)
- [ ] Generate realistic synthetic images
- [ ] Add sensor noise models
- [ ] Implement network latency simulation

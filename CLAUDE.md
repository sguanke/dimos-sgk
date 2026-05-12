# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Go2 robot dog person following system built on the dimos framework. The system uses computer vision to detect and track a specified person, then controls the Go2 robot to follow them while maintaining safe distance and avoiding obstacles.

## Technology Stack

- **Framework**: dimos (distributed intelligent multi-agent operating system)
- **Hardware**: Unitree Go2 robot dog
- **Language**: Python 3.10+
- **Vision**: OpenCV + YOLO for person detection
- **Control**: Go2 SDK for robot control
- **Communication**: ROS2 Humble for inter-process communication

## Architecture

### Component Structure

```
go2_person_following/
├── src/
│   ├── vision/                      # Perception module (perception-agent)
│   │   ├── person_detector.py      # YOLO-based person detection
│   │   ├── person_tracker.py       # Multi-object tracking (DeepSORT)
│   │   └── target_selector.py      # Target person selection logic
│   ├── control/                     # Navigation module (navigation-agent)
│   │   ├── motion_controller.py    # Go2 motion control with PID
│   │   ├── distance_keeper.py      # Maintain following distance
│   │   └── path_planner.py         # Obstacle avoidance path planning
│   ├── localization/                # Localization module (localization-agent)
│   │   ├── odometry.py             # Wheel odometry
│   │   ├── imu_fusion.py           # IMU data fusion
│   │   └── pose_estimator.py       # Robot pose estimation
│   ├── mapping/                     # Mapping module (localization-agent)
│   │   └── local_map.py            # Local obstacle map
│   ├── safety/                      # Safety module (safety-agent)
│   │   ├── safety_monitor.py       # Emergency stop, collision detection
│   │   ├── watchdog.py             # Timeout monitoring
│   │   └── health_checker.py       # System health monitoring
│   ├── dimos_integration/           # Integration module (integration-agent)
│   │   ├── agent_node.py           # Dimos agent wrapper
│   │   └── message_handler.py      # Inter-agent communication
│   └── main.py                      # Entry point (integration-agent)
├── tests/
│   ├── unit/                        # Unit tests (unit-test-agent)
│   ├── integration/                 # Integration tests (integration-test-agent)
│   └── simulation/                  # Simulation tests (simulation-test-agent)
├── config/
│   ├── robot_params.yaml           # Go2 hardware parameters
│   ├── vision_params.yaml          # Detection/tracking parameters
│   └── safety_params.yaml          # Safety thresholds
└── requirements.txt
```

**Agent Responsibilities**:
- **Perception Agent**: Vision and person detection/tracking
- **Navigation Agent**: Motion control and path planning
- **Localization Agent**: Robot pose estimation and local mapping
- **Safety Agent**: Safety monitoring and emergency handling
- **Integration Agent**: Dimos integration and system coordination
- **Test Agents**: Unit, integration, and simulation testing

### Key Design Decisions

**Vision System**
- Use YOLOv8 for real-time person detection (30+ FPS on Go2's compute)
- DeepSORT for robust multi-person tracking
- Target selection: closest person in front of robot initially, then sticky tracking
- Re-identification: use appearance features to re-acquire lost target

**Control System**
- PID controller for distance maintenance (target: 2.0m ± 0.3m)
- Maximum speed: 0.8 m/s (safety constraint)
- Minimum turning radius: 0.5m
- Emergency stop if distance < 0.5m or obstacle detected

**Safety**
- LiDAR-based obstacle detection (if available on Go2)
- Fallback to depth camera if no LiDAR
- Watchdog timer: stop if no valid target for >2 seconds
- Manual override via RC controller always enabled

**Dimos Integration**
- Vision agent: publishes detected person poses
- Control agent: subscribes to poses, publishes motion commands
- Safety agent: monitors all data, can veto motion commands
- Agents communicate via dimos message bus

## Development Commands

### Setup
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Download YOLO weights
python scripts/download_models.py
```

### Testing
```bash
# Run all tests
pytest tests/

# Run specific test suite
pytest tests/unit/
pytest tests/integration/
pytest tests/simulation/

# Run with coverage
pytest --cov=src --cov-report=html tests/

# Run single test
pytest tests/unit/test_person_detector.py::test_detection_accuracy
```

### Running
```bash
# Simulation mode (no hardware)
python src/main.py --mode simulation

# Hardware mode (requires Go2 connection)
python src/main.py --mode hardware --robot-ip 192.168.123.161

# Debug mode with visualization
python src/main.py --mode simulation --debug --visualize
```

### Linting
```bash
# Format code
black src/ tests/

# Type checking
mypy src/

# Linting
pylint src/
```

## Testing Requirements

- **Unit tests**: All core functions must have unit tests
- **Integration tests**: Test agent communication and data flow
- **Simulation tests**: Use recorded video data to test vision pipeline
- **Coverage**: Minimum 80% code coverage
- **Mock hardware**: Use Go2 simulator for control tests

## Code Standards

- Type hints required for all function signatures
- Docstrings required for all public functions (Google style)
- Maximum function length: 50 lines
- Maximum file length: 500 lines
- Use dataclasses for structured data
- Error handling: catch specific exceptions, log all errors

## Safety Requirements

- All motion commands must pass through safety monitor
- Implement graceful degradation (reduce speed if uncertain)
- Log all safety events to file
- Emergency stop must work within 100ms
- Never disable safety checks in production code

## Conflict Resolution Rules

If multiple agents modify the same file:
- **Vision code** (src/vision/): perception-agent has priority
- **Control code** (src/control/): navigation-agent has priority
- **Localization code** (src/localization/, src/mapping/): localization-agent has priority
- **Safety code** (src/safety/): safety-agent has priority, NEVER override safety checks
- **Integration code** (src/dimos_integration/, src/main.py): integration-agent has priority
- **Test code**: respective test-agent has priority
- **Config files**: merge both changes, integration-agent resolves conflicts
- **Documentation**: merge both, prefer more detailed version

**Module Interface Conflicts**:
If agents create conflicting interfaces between modules:
1. Integration-agent identifies the conflict
2. Follow the interface contract defined in .claude/plan.md
3. If plan is ambiguous, prefer the interface that requires fewer changes
4. Document the decision in code comments

## Dependencies

Key packages (see requirements.txt for full list):
- `dimos-sdk>=1.0.0` - Dimos framework
- `unitree-go2-sdk>=2.0.0` - Go2 robot control
- `opencv-python>=4.8.0` - Computer vision
- `ultralytics>=8.0.0` - YOLO models
- `deep-sort-realtime>=1.3.0` - Object tracking
- `rclpy>=3.3.0` - ROS2 Python client

## Hardware Specifications

**Unitree Go2**
- Camera: 1920x1080 @ 30fps
- Compute: NVIDIA Jetson (varies by model)
- Network: WiFi 192.168.123.0/24
- Control frequency: 50Hz
- Battery: ~2 hours runtime

## Known Limitations

- Person detection accuracy drops in low light (<50 lux)
- Tracking may fail if target moves behind obstacles for >3 seconds
- Maximum following speed limited to 0.8 m/s for safety
- Requires flat terrain (stairs/rough terrain not supported)

## Future Enhancements

- Add gesture recognition for commands
- Support multiple robot coordination
- Implement predictive tracking for faster targets
- Add voice feedback for status updates

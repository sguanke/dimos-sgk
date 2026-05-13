# Unit Tests

This directory contains comprehensive unit tests for all modules in the Go2 person following system.

## Test Structure

```
tests/
├── unit/                           # Unit tests for individual modules
│   ├── test_person_detector.py    # Vision: person detection
│   ├── test_person_tracker.py     # Vision: person tracking
│   ├── test_target_selector.py    # Vision: target selection
│   ├── test_motion_controller.py  # Control: motion control
│   ├── test_distance_keeper.py    # Control: distance keeping
│   ├── test_path_planner.py       # Control: path planning
│   ├── test_odometry.py           # Localization: odometry
│   ├── test_imu_fusion.py         # Localization: IMU fusion
│   ├── test_pose_estimator.py     # Localization: pose estimation
│   ├── test_local_map.py          # Mapping: local map
│   ├── test_safety_monitor.py     # Safety: safety monitor (100% coverage)
│   ├── test_watchdog.py           # Safety: watchdog (100% coverage)
│   └── test_health_checker.py     # Safety: health checker (100% coverage)
├── mocks/                          # Mock objects for testing
│   ├── mock_go2.py                # Mock Go2 SDK
│   ├── mock_camera.py             # Mock camera
│   └── mock_dimos.py              # Mock dimos message bus
├── integration/                    # Integration tests
├── simulation/                     # Simulation tests
├── fixtures/                       # Test data and fixtures
├── conftest.py                     # Pytest configuration
└── requirements-test.txt           # Test dependencies

```

## Running Tests

### Run all unit tests
```bash
pytest tests/unit/
```

### Run specific test file
```bash
pytest tests/unit/test_safety_monitor.py
```

### Run with coverage report
```bash
pytest --cov=src --cov-report=html --cov-report=term
```

### Run only safety tests (require 100% coverage)
```bash
pytest -m safety tests/unit/
```

### Run tests in parallel
```bash
pytest -n auto tests/unit/
```

## Coverage Requirements

- **Overall coverage**: >80%
- **Safety modules**: 100% coverage (safety_monitor, watchdog, health_checker)
- **Critical modules**: >90% coverage (motion_controller, distance_keeper)

## Test Markers

Tests are marked with pytest markers for selective execution:

- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.simulation` - Simulation tests
- `@pytest.mark.safety` - Safety-critical tests requiring 100% coverage

## Mock Objects

Mock implementations are provided for hardware and external dependencies:

- **MockGo2SDK**: Simulates Go2 robot SDK without hardware
- **MockCamera**: Provides test frames without camera hardware
- **MockMessageBus**: Simulates dimos message bus for agent communication

## Writing New Tests

Follow the Arrange-Act-Assert pattern:

```python
def test_function_name():
    # Arrange: setup test data
    input_data = create_test_input()
    
    # Act: call function under test
    result = function_under_test(input_data)
    
    # Assert: verify results
    assert result == expected_output
```

### Test Coverage Guidelines

1. **Normal cases**: Test typical usage scenarios
2. **Edge cases**: Test boundary conditions (zero, negative, max values)
3. **Error cases**: Test error handling and exceptions
4. **Thread safety**: Test concurrent access where applicable

## Continuous Integration

Tests are automatically run on:
- Every commit
- Pull requests
- Before merging to main

CI pipeline fails if:
- Any test fails
- Coverage drops below 80%
- Safety module coverage is below 100%

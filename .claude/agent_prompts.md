# Agent Prompts

This file contains detailed prompts for each agent in the multi-agent workflow.

---

## Perception Agent

**Role**: Implement the vision and person detection/tracking system

**Input**:
- CLAUDE.md (architecture and requirements)
- .claude/plan.md (implementation plan from planning phase)

**Output**:
- `src/vision/person_detector.py` - YOLO-based person detection
- `src/vision/person_tracker.py` - DeepSORT multi-object tracking
- `src/vision/target_selector.py` - Target person selection logic
- `config/vision_params.yaml` - Vision configuration

**Detailed Instructions**:

1. **person_detector.py**
   - Use YOLOv8 for real-time person detection (30+ FPS)
   - Input: camera frame (1920x1080)
   - Output: list of detected person bounding boxes with confidence scores
   - Filter detections: confidence > 0.5, class = "person"
   - Implement non-maximum suppression (NMS)

2. **person_tracker.py**
   - Use DeepSORT for robust multi-person tracking
   - Assign unique IDs to each detected person
   - Maintain tracking across frames (handle occlusion up to 30 frames)
   - Extract appearance features for re-identification
   - Output: tracked persons with IDs, bounding boxes, velocities

3. **target_selector.py**
   - Initial selection: closest person in front of robot (within 60° FOV)
   - Sticky tracking: once selected, maintain target even if others are closer
   - Re-acquisition: use appearance features if target lost for <3 seconds
   - Publish target person ID and position to dimos message bus

4. **vision_params.yaml**
   ```yaml
   yolo:
     model: "yolov8n.pt"
     confidence_threshold: 0.5
     nms_threshold: 0.4
   
   deepsort:
     max_age: 30
     n_init: 3
     max_iou_distance: 0.7
   
   target_selection:
     fov_angle: 60  # degrees
     max_distance: 10.0  # meters
     reacquisition_timeout: 3.0  # seconds
   ```

**Code Quality**:
- Type hints for all functions
- Docstrings (Google style)
- Max function length: 50 lines
- Use dataclasses for Person, Detection, Track objects
- Log all detection/tracking events

**Do NOT**:
- Implement control logic (that's navigation-agent's job)
- Write tests (handled by test agents)
- Hardcode parameters (use config file)

---

## Navigation Agent

**Role**: Implement motion control and path planning

**Input**:
- CLAUDE.md (architecture and requirements)
- .claude/plan.md (implementation plan)

**Output**:
- `src/control/motion_controller.py` - PID-based motion control
- `src/control/distance_keeper.py` - Maintain following distance
- `src/control/path_planner.py` - Obstacle avoidance path planning
- `config/robot_params.yaml` - Robot configuration

**Detailed Instructions**:

1. **motion_controller.py**
   - Implement PID controller for linear and angular velocity
   - Input: target position (from perception), robot pose (from localization)
   - Output: velocity commands (linear_x, angular_z)
   - Constraints: max speed 0.8 m/s, max angular 1.0 rad/s
   - Use Go2 SDK to send commands at 50Hz

2. **distance_keeper.py**
   - Target distance: 2.0m ± 0.3m from target person
   - If distance < 1.7m: slow down or stop
   - If distance > 2.3m: speed up (max 0.8 m/s)
   - If distance < 0.5m: emergency stop (trigger safety monitor)
   - Smooth acceleration/deceleration (max accel: 0.5 m/s²)

3. **path_planner.py**
   - Use local obstacle map from localization-agent
   - Dynamic Window Approach (DWA) for local planning
   - Avoid obstacles while maintaining target following
   - Minimum clearance: 0.3m from obstacles
   - Re-plan at 10Hz

4. **robot_params.yaml**
   ```yaml
   go2:
     max_linear_velocity: 0.8  # m/s
     max_angular_velocity: 1.0  # rad/s
     max_acceleration: 0.5  # m/s²
     control_frequency: 50  # Hz
     
   pid:
     linear:
       kp: 0.5
       ki: 0.01
       kd: 0.1
     angular:
       kp: 1.0
       ki: 0.02
       kd: 0.15
   
   following:
     target_distance: 2.0  # meters
     distance_tolerance: 0.3  # meters
     emergency_distance: 0.5  # meters
   ```

**Code Quality**:
- Type hints and docstrings
- Max function length: 50 lines
- Use dataclasses for VelocityCommand, PIDState
- Log all motion commands

**Safety**:
- All commands must be validated before sending to robot
- Implement velocity ramping (no sudden changes)
- Respect robot kinematic constraints

**Do NOT**:
- Implement safety checks (that's safety-agent's job)
- Write tests
- Bypass Go2 SDK safety features

---

## Localization Agent

**Role**: Implement robot pose estimation and local mapping

**Input**:
- CLAUDE.md (architecture and requirements)
- .claude/plan.md (implementation plan)

**Output**:
- `src/localization/odometry.py` - Wheel odometry
- `src/localization/imu_fusion.py` - IMU data fusion
- `src/localization/pose_estimator.py` - Robot pose estimation
- `src/mapping/local_map.py` - Local obstacle map

**Detailed Instructions**:

1. **odometry.py**
   - Read wheel encoder data from Go2 SDK
   - Compute incremental pose changes (dx, dy, dθ)
   - Accumulate to get odometry pose estimate
   - Publish at 50Hz
   - Note: odometry drifts over time, use IMU for correction

2. **imu_fusion.py**
   - Read IMU data (accelerometer, gyroscope) from Go2 SDK
   - Use complementary filter or EKF to fuse with odometry
   - Correct orientation drift using gyroscope
   - Detect sudden movements (falls, collisions)
   - Publish fused pose at 50Hz

3. **pose_estimator.py**
   - Combine odometry and IMU data
   - Maintain robot pose (x, y, θ) in world frame
   - Provide pose covariance (uncertainty estimate)
   - Reset pose on user command
   - Publish to dimos message bus

4. **local_map.py**
   - Build 2D occupancy grid around robot (10m × 10m, 0.1m resolution)
   - Use depth camera or LiDAR data (if available on Go2)
   - Update map at 10Hz
   - Mark obstacles, free space, unknown space
   - Provide to navigation-agent for path planning

**Code Quality**:
- Type hints and docstrings
- Use numpy for efficient computation
- Dataclasses for Pose, IMUData, OccupancyGrid
- Log pose estimates and map updates

**Do NOT**:
- Implement SLAM (out of scope for this project)
- Write tests
- Use global localization (only local odometry needed)

---

## Safety Agent

**Role**: Implement safety monitoring and emergency handling

**Input**:
- CLAUDE.md (architecture and requirements, especially safety requirements)
- .claude/plan.md (implementation plan)

**Output**:
- `src/safety/safety_monitor.py` - Emergency stop, collision detection
- `src/safety/watchdog.py` - Timeout monitoring
- `src/safety/health_checker.py` - System health monitoring
- `config/safety_params.yaml` - Safety configuration

**Detailed Instructions**:

1. **safety_monitor.py** (CRITICAL)
   - Subscribe to all motion commands from navigation-agent
   - Validate each command before forwarding to robot:
     - Check velocity limits
     - Check distance to obstacles
     - Check distance to target person
   - Veto commands that violate safety constraints
   - Implement emergency stop (triggered if distance < 0.5m)
   - Emergency stop must execute within 100ms
   - Log ALL safety events to file
   - Location: src/safety/safety_monitor.py

2. **watchdog.py**
   - Monitor all critical components (perception, navigation, localization)
   - If no valid target detected for >2 seconds: stop robot
   - If no pose update for >0.5 seconds: stop robot
   - If no motion command for >1 second: assume navigation failed, stop
   - Heartbeat mechanism: each component must send heartbeat every 0.5s
   - Log all timeout events

3. **health_checker.py**
   - Monitor system health:
     - CPU usage (warn if >80%)
     - Memory usage (warn if >90%)
     - Camera frame rate (warn if <20 FPS)
     - Battery level (warn if <20%, stop if <10%)
     - Network latency to Go2 (warn if >100ms)
   - Publish health status to dimos message bus
   - Trigger graceful degradation if needed (e.g., reduce speed if CPU high)

4. **safety_params.yaml**
   ```yaml
   safety_monitor:
     max_linear_velocity: 0.8  # m/s
     max_angular_velocity: 1.0  # rad/s
     min_obstacle_distance: 0.3  # meters
     emergency_stop_distance: 0.5  # meters
     emergency_stop_timeout: 0.1  # seconds
   
   watchdog:
     target_timeout: 2.0  # seconds
     pose_timeout: 0.5  # seconds
     command_timeout: 1.0  # seconds
     heartbeat_interval: 0.5  # seconds
   
   health:
     cpu_warning_threshold: 80  # percent
     memory_warning_threshold: 90  # percent
     fps_warning_threshold: 20  # fps
     battery_warning_threshold: 20  # percent
     battery_critical_threshold: 10  # percent
   ```

**Code Quality**:
- Type hints and docstrings
- Max function length: 50 lines
- Extensive logging (all safety events)
- Use threading for concurrent monitoring

**CRITICAL SAFETY REQUIREMENTS**:
- NEVER disable safety checks
- NEVER allow commands that violate constraints
- Emergency stop has absolute priority
- Log everything for post-incident analysis
- Fail-safe: if in doubt, stop the robot

**Do NOT**:
- Skip any safety checks
- Allow unsafe commands "just this once"
- Write tests (handled by test agents)
- Optimize for performance at the cost of safety

---

## Integration Agent

**Role**: Integrate all modules and create dimos communication layer

**Input**:
- Code from perception-agent's worktree
- Code from navigation-agent's worktree
- Code from localization-agent's worktree
- Code from safety-agent's worktree
- CLAUDE.md (architecture)
- .claude/plan.md (implementation plan)

**Output**:
- `src/dimos_integration/agent_node.py` - Dimos agent wrapper
- `src/dimos_integration/message_handler.py` - Inter-agent communication
- `src/main.py` - Entry point
- `requirements.txt` - All dependencies
- `README.md` - Setup and usage instructions

**Detailed Instructions**:

1. **agent_node.py**
   - Wrap each module as a dimos agent:
     - PerceptionAgent (runs person_detector, person_tracker, target_selector)
     - NavigationAgent (runs motion_controller, distance_keeper, path_planner)
     - LocalizationAgent (runs odometry, imu_fusion, pose_estimator, local_map)
     - SafetyAgent (runs safety_monitor, watchdog, health_checker)
   - Each agent runs in separate thread/process
   - Implement dimos agent lifecycle (init, start, stop, shutdown)
   - Handle agent failures gracefully

2. **message_handler.py**
   - Define message types:
     - PersonDetection (from perception to navigation)
     - RobotPose (from localization to navigation)
     - MotionCommand (from navigation to safety)
     - SafetyEvent (from safety to all)
     - HealthStatus (from safety to all)
   - Implement dimos message bus communication
   - Use publish-subscribe pattern
   - Add message timestamps and sequence numbers

3. **main.py**
   - Parse command-line arguments:
     - --mode (simulation/hardware)
     - --robot-ip (for hardware mode)
     - --debug (enable debug logging)
     - --visualize (show camera feed with detections)
   - Load configuration files
   - Initialize all agents in correct order:
     1. LocalizationAgent
     2. PerceptionAgent
     3. SafetyAgent
     4. NavigationAgent
   - Start dimos message bus
   - Handle Ctrl+C gracefully (shutdown all agents)
   - Log startup and shutdown events

4. **requirements.txt**
   ```
   dimos-sdk>=1.0.0
   unitree-go2-sdk>=2.0.0
   opencv-python>=4.8.0
   ultralytics>=8.0.0
   deep-sort-realtime>=1.3.0
   rclpy>=3.3.0
   numpy>=1.24.0
   pyyaml>=6.0
   ```

5. **README.md**
   - Project overview
   - Hardware requirements (Go2 robot)
   - Installation instructions
   - Configuration guide
   - Usage examples (simulation and hardware modes)
   - Troubleshooting section
   - Architecture diagram

**Integration Checklist**:
- [ ] All modules import correctly
- [ ] Message types are consistent across agents
- [ ] Agent startup order is correct
- [ ] Graceful shutdown works
- [ ] Configuration files are loaded
- [ ] Simulation mode works without hardware
- [ ] Hardware mode connects to Go2

**Do NOT**:
- Modify code from other agents (only integrate)
- Write tests
- Skip error handling in integration layer

---

## Unit Test Agent

**Role**: Write unit tests for all modules

**Input**:
- Source code from all implementation agents' worktrees
- CLAUDE.md (testing requirements)

**Output**:
- `tests/unit/test_person_detector.py`
- `tests/unit/test_person_tracker.py`
- `tests/unit/test_target_selector.py`
- `tests/unit/test_motion_controller.py`
- `tests/unit/test_distance_keeper.py`
- `tests/unit/test_path_planner.py`
- `tests/unit/test_odometry.py`
- `tests/unit/test_imu_fusion.py`
- `tests/unit/test_pose_estimator.py`
- `tests/unit/test_local_map.py`
- `tests/unit/test_safety_monitor.py`
- `tests/unit/test_watchdog.py`
- `tests/unit/test_health_checker.py`
- `tests/mocks/` - Mock objects
- `pytest.ini` - Pytest configuration

**Detailed Instructions**:

1. **Test Structure** (for each module)
   ```python
   import pytest
   from unittest.mock import Mock, patch
   
   def test_function_name_normal_case():
       # Arrange: setup test data
       # Act: call function under test
       # Assert: verify results
   
   def test_function_name_edge_case():
       # Test boundary conditions
   
   def test_function_name_error_case():
       # Test error handling
   ```

2. **Mock Strategy**
   - Create `tests/mocks/mock_go2.py` - Mock Go2 SDK
   - Create `tests/mocks/mock_camera.py` - Mock camera
   - Create `tests/mocks/mock_dimos.py` - Mock dimos message bus
   - Use `unittest.mock` for simple mocks
   - Use fixtures for reusable test data

3. **Coverage Requirements**
   - Overall coverage: >80%
   - Safety modules: 100% coverage
   - Use `pytest-cov` to measure
   - Generate HTML coverage report

4. **Test Examples**
   - Test person_detector with sample images
   - Test motion_controller with various target positions
   - Test safety_monitor with unsafe commands (should be vetoed)
   - Test watchdog timeout behavior
   - Test all error conditions

5. **pytest.ini**
   ```ini
   [pytest]
   testpaths = tests/unit
   python_files = test_*.py
   python_classes = Test*
   python_functions = test_*
   addopts = --cov=src --cov-report=html --cov-report=term
   ```

**Do NOT**:
- Modify source code
- Skip edge cases
- Write tests that depend on external services
- Hardcode test data paths

---

## Integration Test Agent

**Role**: Write integration tests for module interactions

**Input**:
- Source code from all implementation agents' worktrees
- CLAUDE.md (testing requirements)

**Output**:
- `tests/integration/test_perception_to_navigation.py`
- `tests/integration/test_safety_integration.py`
- `tests/integration/test_dimos_communication.py`
- `tests/integration/test_full_pipeline.py`
- `tests/fixtures/` - Test fixtures

**Detailed Instructions**:

1. **test_perception_to_navigation.py**
   - Test data flow from perception to navigation
   - Mock camera, use real detection/tracking code
   - Verify navigation receives correct target positions
   - Test with multiple people in scene

2. **test_safety_integration.py**
   - Test safety monitor vetoing unsafe commands
   - Test emergency stop trigger
   - Test watchdog timeout behavior
   - Test health checker warnings

3. **test_dimos_communication.py**
   - Test message passing between agents
   - Test publish-subscribe pattern
   - Test message ordering and timestamps
   - Test agent startup and shutdown

4. **test_full_pipeline.py**
   - Test complete system with all modules
   - Use recorded video data
   - Mock Go2 hardware
   - Verify robot follows detected person
   - Test various scenarios:
     - Person walks straight
     - Person turns
     - Person stops
     - Person temporarily occluded

5. **Test Fixtures**
   - Sample images with people
   - Recorded video sequences
   - Mock sensor data (IMU, odometry)
   - Configuration files for testing

**Do NOT**:
- Modify source code
- Skip error scenarios
- Use real hardware (mock it)

---

## Simulation Test Agent

**Role**: Write simulation tests for end-to-end scenarios

**Input**:
- Source code from all implementation agents' worktrees
- CLAUDE.md (testing requirements)

**Output**:
- `tests/simulation/test_following_scenarios.py`
- `tests/simulation/test_obstacle_avoidance.py`
- `tests/simulation/test_edge_cases.py`
- `tests/simulation/fixtures/` - Test data (videos, maps)

**Detailed Instructions**:

1. **test_following_scenarios.py**
   - Test person following in various scenarios:
     - Person walks at different speeds (0.5, 1.0, 1.5 m/s)
     - Person walks in straight line, curves, circles
     - Person stops suddenly
     - Person changes direction
   - Use Go2 simulator (if available) or mock
   - Verify robot maintains target distance
   - Measure following accuracy

2. **test_obstacle_avoidance.py**
   - Test navigation around obstacles
   - Create test maps with obstacles
   - Verify robot avoids collisions
   - Verify robot still follows person while avoiding obstacles

3. **test_edge_cases.py**
   - Multiple people in scene (verify correct target selection)
   - Target person leaves FOV (verify robot stops)
   - Target person re-enters FOV (verify re-acquisition)
   - Low light conditions (verify degraded performance)
   - Occlusion (verify tracking recovery)
   - Battery low (verify graceful shutdown)

4. **Test Data**
   - Record video sequences for each scenario
   - Create synthetic test maps
   - Generate mock sensor data

5. **Metrics**
   - Following distance error (should be < 0.3m)
   - Tracking success rate (should be > 95%)
   - Collision avoidance success rate (should be 100%)
   - Response time to person movements (should be < 0.5s)

**Do NOT**:
- Modify source code
- Skip edge cases
- Use real hardware (use simulator)
- Hardcode test data paths

---

## Review Agent

**Role**: Review all implementations and tests for quality and compliance

**Input**:
- Source code from all implementation agents
- Test code from all test agents
- CLAUDE.md (requirements and standards)

**Output**:
- `.claude/state/review.md` - Comprehensive review report

**Review Checklist**:

### 1. Architecture Compliance
- [ ] All modules follow CLAUDE.md structure
- [ ] Correct technology stack used
- [ ] Dimos integration is correct
- [ ] Module interfaces are consistent

### 2. Code Quality (per module)
- [ ] Type hints for all functions
- [ ] Docstrings for all public functions
- [ ] No function exceeds 50 lines
- [ ] No file exceeds 500 lines
- [ ] Dataclasses used for structured data
- [ ] No hardcoded values

### 3. Safety Requirements (CRITICAL)
- [ ] All motion commands go through safety_monitor
- [ ] Emergency stop implemented and tested
- [ ] Watchdog timer present
- [ ] Safety events are logged
- [ ] NO disabled safety checks anywhere

### 4. Error Handling
- [ ] Specific exceptions caught
- [ ] All errors logged
- [ ] Graceful degradation implemented
- [ ] No bare except clauses

### 5. Testing
- [ ] Unit tests for all modules
- [ ] Integration tests present
- [ ] Simulation tests present
- [ ] Coverage >80% (100% for safety modules)
- [ ] Tests use proper mocking

### 6. Integration
- [ ] All modules integrate correctly
- [ ] Message types are consistent
- [ ] Agent startup order is correct
- [ ] Graceful shutdown works

### 7. Documentation
- [ ] README.md is complete
- [ ] Setup instructions are clear
- [ ] Usage examples provided
- [ ] Configuration documented

### 8. Dependencies
- [ ] requirements.txt is complete
- [ ] Version constraints specified
- [ ] No unnecessary dependencies

**Review Report Format**:

```markdown
# Code Review Report

## Summary
[Pass/Fail] - [Brief summary]

## Module Reviews

### Perception Module
- Architecture: [Pass/Fail]
- Code Quality: [Pass/Fail]
- Issues: [List]

### Navigation Module
- Architecture: [Pass/Fail]
- Code Quality: [Pass/Fail]
- Issues: [List]

### Localization Module
- Architecture: [Pass/Fail]
- Code Quality: [Pass/Fail]
- Issues: [List]

### Safety Module (CRITICAL)
- Architecture: [Pass/Fail]
- Code Quality: [Pass/Fail]
- Safety Compliance: [Pass/Fail]
- Issues: [List]

### Integration Module
- Architecture: [Pass/Fail]
- Code Quality: [Pass/Fail]
- Issues: [List]

## Testing Review
- Unit Tests: [Pass/Fail] - Coverage: [X%]
- Integration Tests: [Pass/Fail]
- Simulation Tests: [Pass/Fail]
- Issues: [List]

## Critical Issues (High Severity)
1. [Issue] - Module: [X] - Impact: [Y]

## Medium Issues
1. [Issue] - Module: [X]

## Low Issues
1. [Issue] - Module: [X]

## Recommendations
1. [Recommendation]

## Final Decision
[PASS/FAIL] - [Justification]

If FAIL: [List of blocking issues that must be fixed]
```

**Pass Criteria**:
- NO high-severity issues
- ALL safety requirements met
- Test coverage >80%
- All modules integrate correctly

**Automatic FAIL Conditions**:
- Any disabled safety check
- Missing emergency stop
- Safety module coverage <100%
- Hardcoded safety parameters

**Do NOT**:
- Modify any code
- Be lenient on safety issues
- Skip any checklist items
- Approve code with known bugs

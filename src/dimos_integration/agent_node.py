"""Dimos agent wrappers for all system modules.

This module wraps each functional module (perception, navigation, localization,
safety) as a dimos agent that runs in a separate thread and communicates via
the message bus.
"""

import logging
import time
from abc import ABC, abstractmethod
from threading import Thread, Event
from typing import Optional

import cv2
import numpy as np

from ..vision.person_detector import PersonDetector
from ..vision.person_tracker import PersonTracker
from ..vision.target_selector import TargetSelector
from ..control.motion_controller import MotionController, TargetPosition, RobotPose, VelocityCommand as ControlVelocityCommand
from ..control.distance_keeper import DistanceKeeper
from ..control.path_planner import PathPlanner
from ..localization.pose_estimator import PoseEstimator, WheelEncoderData
from ..localization.imu_fusion import IMUData
from ..mapping.local_map import LocalMap
from ..safety.safety_monitor import SafetyMonitor, VelocityCommand as SafetyVelocityCommand
from ..safety.watchdog import Watchdog, ComponentType
from ..safety.health_checker import HealthChecker

from .message_handler import (
    MessageBus,
    MessageType,
    PersonDetectionMessage,
    RobotPoseMessage,
    MotionCommandMessage,
    SafetyEventMessage,
    HealthStatusMessage,
)


logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Base class for all dimos agents.

    Implements common agent lifecycle methods and threading.
    """

    def __init__(self, name: str, message_bus: MessageBus, update_rate: float = 10.0):
        """Initialize base agent.

        Args:
            name: Agent name
            message_bus: Message bus for communication
            update_rate: Update frequency in Hz
        """
        self.name = name
        self.message_bus = message_bus
        self.update_rate = update_rate
        self.update_period = 1.0 / update_rate

        self._running = False
        self._thread: Optional[Thread] = None
        self._stop_event = Event()
        self._logger = logging.getLogger(f"{__name__}.{name}")

        self._logger.info(f"{name} agent initialized")

    def start(self) -> None:
        """Start agent thread."""
        if self._running:
            self._logger.warning(f"{self.name} already running")
            return

        self._running = True
        self._stop_event.clear()
        self._thread = Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._logger.info(f"{self.name} agent started")

    def stop(self) -> None:
        """Stop agent thread."""
        if not self._running:
            return

        self._running = False
        self._stop_event.set()

        if self._thread:
            self._thread.join(timeout=5.0)
            self._logger.info(f"{self.name} agent stopped")

    def is_running(self) -> bool:
        """Check if agent is running."""
        return self._running

    def _run_loop(self) -> None:
        """Main agent loop running in separate thread."""
        self._logger.info(f"{self.name} agent loop started")

        while self._running:
            try:
                start_time = time.time()

                # Run agent update
                self._update()

                # Sleep to maintain update rate
                elapsed = time.time() - start_time
                sleep_time = max(0, self.update_period - elapsed)
                if sleep_time > 0:
                    self._stop_event.wait(sleep_time)

            except Exception as e:
                self._logger.error(f"Error in {self.name} update loop: {e}", exc_info=True)
                time.sleep(0.1)

        self._logger.info(f"{self.name} agent loop ended")

    @abstractmethod
    def _update(self) -> None:
        """Update method called at each iteration.

        Must be implemented by subclasses.
        """
        pass


class PerceptionAgent(BaseAgent):
    """Perception agent for person detection and tracking.

    Runs person detector, tracker, and target selector.
    Publishes PersonDetectionMessage to message bus.
    """

    def __init__(
        self,
        message_bus: MessageBus,
        camera_source: int = 0,
        update_rate: float = 30.0,
        config_path: str = "config/vision_params.yaml"
    ):
        """Initialize perception agent.

        Args:
            message_bus: Message bus for communication
            camera_source: Camera device index or video file path
            update_rate: Update frequency in Hz
            config_path: Path to vision configuration
        """
        super().__init__("PerceptionAgent", message_bus, update_rate)

        # Initialize vision modules
        self.detector = PersonDetector()
        self.tracker = PersonTracker()
        self.target_selector = TargetSelector()

        # Camera
        self.camera_source = camera_source
        self.camera: Optional[cv2.VideoCapture] = None

        self._logger.info("PerceptionAgent modules initialized")

    def start(self) -> None:
        """Start perception agent and open camera."""
        # Open camera
        self.camera = cv2.VideoCapture(self.camera_source)
        if not self.camera.isOpened():
            self._logger.error(f"Failed to open camera: {self.camera_source}")
            raise RuntimeError("Camera initialization failed")

        self._logger.info(f"Camera opened: {self.camera_source}")
        super().start()

    def stop(self) -> None:
        """Stop perception agent and release camera."""
        super().stop()
        if self.camera:
            self.camera.release()
            self._logger.info("Camera released")

    def _update(self) -> None:
        """Perception update: detect, track, and select target."""
        if not self.camera or not self.camera.isOpened():
            return

        # Capture frame
        ret, frame = self.camera.read()
        if not ret or frame is None:
            self._logger.warning("Failed to capture frame")
            return

        # Detect persons
        detections = self.detector.detect(frame)

        # Track persons
        tracks = self.tracker.update(frame, detections)

        # Select target
        target = self.target_selector.select_target(tracks)

        # Publish target detection message
        msg = PersonDetectionMessage(source_agent=self.name)
        if target:
            msg.target_id = target.track_id
            msg.bbox = target.bbox
            msg.distance = target.distance
            msg.angle = target.angle
            msg.confidence = target.confidence
            msg.velocity = target.velocity

        self.message_bus.publish(MessageType.PERSON_DETECTION, msg)


class LocalizationAgent(BaseAgent):
    """Localization agent for pose estimation and mapping.

    Runs odometry, IMU fusion, pose estimator, and local map.
    Publishes RobotPoseMessage to message bus.
    """

    def __init__(
        self,
        message_bus: MessageBus,
        update_rate: float = 50.0,
        go2_sdk=None
    ):
        """Initialize localization agent.

        Args:
            message_bus: Message bus for communication
            update_rate: Update frequency in Hz
            go2_sdk: Go2 SDK instance for sensor data (optional for simulation)
        """
        super().__init__("LocalizationAgent", message_bus, update_rate)

        # Initialize localization modules
        self.pose_estimator = PoseEstimator(publish_rate=update_rate)
        self.local_map = LocalMap()

        # Go2 SDK for sensor data
        self.go2_sdk = go2_sdk

        self._logger.info("LocalizationAgent modules initialized")

    def _update(self) -> None:
        """Localization update: estimate pose and update map."""
        # Get sensor data from Go2 SDK (or simulate)
        encoder_data = self._get_encoder_data()
        imu_data = self._get_imu_data()

        # Update pose estimate
        pose = self.pose_estimator.update(encoder_data, imu_data)

        # Update local map (if depth data available)
        # depth_data = self._get_depth_data()
        # if depth_data is not None:
        #     self.local_map.update(pose, depth_data)

        # Publish robot pose message
        msg = RobotPoseMessage(
            source_agent=self.name,
            x=pose.x,
            y=pose.y,
            theta=pose.theta,
            covariance=pose.covariance
        )
        self.message_bus.publish(MessageType.ROBOT_POSE, msg)

    def _get_encoder_data(self) -> WheelEncoderData:
        """Get wheel encoder data from Go2 SDK or simulate."""
        if self.go2_sdk:
            # Get real encoder data from Go2
            pass

        # Simulate encoder data
        return WheelEncoderData(
            left_ticks=0,
            right_ticks=0,
            timestamp=time.time()
        )

    def _get_imu_data(self) -> IMUData:
        """Get IMU data from Go2 SDK or simulate."""
        if self.go2_sdk:
            # Get real IMU data from Go2
            pass

        # Simulate IMU data
        return IMUData(
            accel_x=0.0,
            accel_y=0.0,
            accel_z=9.81,
            gyro_x=0.0,
            gyro_y=0.0,
            gyro_z=0.0,
            timestamp=time.time()
        )


class NavigationAgent(BaseAgent):
    """Navigation agent for motion control and path planning.

    Subscribes to PersonDetectionMessage and RobotPoseMessage.
    Publishes MotionCommandMessage to message bus.
    """

    def __init__(
        self,
        message_bus: MessageBus,
        update_rate: float = 50.0,
        config_path: str = "config/robot_params.yaml"
    ):
        """Initialize navigation agent.

        Args:
            message_bus: Message bus for communication
            update_rate: Update frequency in Hz
            config_path: Path to robot configuration
        """
        super().__init__("NavigationAgent", message_bus, update_rate)

        # Initialize navigation modules
        self.motion_controller = MotionController(config_path)
        self.distance_keeper = DistanceKeeper(config_path)
        self.path_planner = PathPlanner()

        # Latest messages from other agents
        self.latest_target: Optional[PersonDetectionMessage] = None
        self.latest_pose: Optional[RobotPoseMessage] = None

        # Subscribe to messages
        self.message_bus.subscribe(
            MessageType.PERSON_DETECTION,
            self._on_person_detection
        )
        self.message_bus.subscribe(
            MessageType.ROBOT_POSE,
            self._on_robot_pose
        )

        self._logger.info("NavigationAgent modules initialized")

    def _on_person_detection(self, msg: PersonDetectionMessage) -> None:
        """Handle person detection message."""
        self.latest_target = msg

    def _on_robot_pose(self, msg: RobotPoseMessage) -> None:
        """Handle robot pose message."""
        self.latest_pose = msg

    def _update(self) -> None:
        """Navigation update: compute and publish motion command."""
        # Check if we have target and pose
        if not self.latest_target or not self.latest_pose:
            # No target or pose, send stop command
            command = self.motion_controller.stop()
            self._publish_command(command)
            return

        # Check if target is valid
        if self.latest_target.target_id is None:
            # No valid target, send stop command
            command = self.motion_controller.stop()
            self._publish_command(command)
            return

        # Create target position
        target_pos = TargetPosition(
            distance=self.latest_target.distance or 2.0,
            angle=np.radians(self.latest_target.angle or 0.0),
            timestamp=self.latest_target.timestamp
        )

        # Create robot pose
        robot_pose = RobotPose(
            x=self.latest_pose.x,
            y=self.latest_pose.y,
            theta=self.latest_pose.theta,
            timestamp=self.latest_pose.timestamp
        )

        # Compute velocity command
        command = self.motion_controller.compute_velocity(target_pos, robot_pose)

        # Apply distance keeping adjustments
        distance_cmd = self.distance_keeper.compute_distance_command(target_pos.distance)

        # If emergency stop or should stop, override command
        if distance_cmd.emergency_stop or distance_cmd.should_stop:
            command = self.motion_controller.stop()
        else:
            # Scale velocity based on distance command
            scale = min(1.0, distance_cmd.target_linear_velocity / (abs(command.linear_x) + 0.001))
            command.linear_x *= scale

        # Publish command
        self._publish_command(command)

    def _publish_command(self, command: VelocityCommand) -> None:
        """Publish motion command message."""
        msg = MotionCommandMessage(
            source_agent=self.name,
            linear_x=command.linear_x,
            angular_z=command.angular_z,
            validated=False
        )
        self.message_bus.publish(MessageType.MOTION_COMMAND, msg)


class SafetyAgent(BaseAgent):
    """Safety agent for monitoring and validation.

    Subscribes to MotionCommandMessage and validates all commands.
    Runs safety monitor, watchdog, and health checker.
    Publishes SafetyEventMessage and HealthStatusMessage.
    """

    def __init__(
        self,
        message_bus: MessageBus,
        update_rate: float = 50.0,
        config_path: str = "config/safety_params.yaml",
        go2_sdk=None
    ):
        """Initialize safety agent.

        Args:
            message_bus: Message bus for communication
            update_rate: Update frequency in Hz
            config_path: Path to safety configuration
            go2_sdk: Go2 SDK instance for sending commands
        """
        super().__init__("SafetyAgent", message_bus, update_rate)

        # Initialize safety modules
        self.safety_monitor = SafetyMonitor(config_path)
        self.watchdog = Watchdog(config_path, self._on_watchdog_timeout)
        self.health_checker = HealthChecker(config_path)

        # Go2 SDK for sending validated commands
        self.go2_sdk = go2_sdk

        # Latest motion command
        self.latest_command: Optional[MotionCommandMessage] = None
        self.latest_target: Optional[PersonDetectionMessage] = None

        # Subscribe to messages
        self.message_bus.subscribe(
            MessageType.MOTION_COMMAND,
            self._on_motion_command
        )
        self.message_bus.subscribe(
            MessageType.PERSON_DETECTION,
            self._on_person_detection
        )

        self._logger.info("SafetyAgent modules initialized")

    def start(self) -> None:
        """Start safety agent and watchdog."""
        super().start()
        self.watchdog.start()
        self._logger.info("Watchdog started")

    def stop(self) -> None:
        """Stop safety agent and watchdog."""
        self.watchdog.stop()
        super().stop()
        self._logger.info("Watchdog stopped")

    def _on_motion_command(self, msg: MotionCommandMessage) -> None:
        """Handle motion command message."""
        self.latest_command = msg

    def _on_person_detection(self, msg: PersonDetectionMessage) -> None:
        """Handle person detection message."""
        self.latest_target = msg
        if msg.target_id is not None:
            self.watchdog.update_target_detected()

    def _on_watchdog_timeout(self, component_type: ComponentType, reason: str) -> None:
        """Handle watchdog timeout."""
        self._logger.critical(f"Watchdog timeout: {component_type.value} - {reason}")

        # Trigger emergency stop
        self.safety_monitor._trigger_emergency_stop(reason)

        # Publish safety event
        msg = SafetyEventMessage(
            source_agent=self.name,
            level="emergency_stop",
            reason=f"Watchdog timeout: {reason}",
            emergency_stop_active=True
        )
        self.message_bus.publish(MessageType.SAFETY_EVENT, msg)

    def _update(self) -> None:
        """Safety update: validate commands and check health."""
        # Validate motion command if available
        if self.latest_command and not self.latest_command.validated:
            self._validate_and_execute_command()

        # Update watchdog
        self.watchdog.heartbeat(ComponentType.PERCEPTION)
        self.watchdog.heartbeat(ComponentType.NAVIGATION)
        self.watchdog.heartbeat(ComponentType.LOCALIZATION)

        # Check system health
        health = self.health_checker.get_health_report()

        # Publish health status
        msg = HealthStatusMessage(
            source_agent=self.name,
            cpu_usage=health.metrics.cpu_percent,
            memory_usage=health.metrics.memory_percent,
            camera_fps=health.metrics.camera_fps,
            battery_level=health.metrics.battery_percent,
            all_components_healthy=self.watchdog.is_all_healthy(),
            component_status=self.watchdog.get_status()
        )
        self.message_bus.publish(MessageType.HEALTH_STATUS, msg)

    def _validate_and_execute_command(self) -> None:
        """Validate motion command and send to robot if safe."""
        if not self.latest_command:
            return

        # Create velocity command for validation
        command = SafetyVelocityCommand(
            linear_x=self.latest_command.linear_x,
            angular_z=self.latest_command.angular_z,
            timestamp=self.latest_command.timestamp
        )

        # Get distance to target
        distance_to_target = None
        if self.latest_target and self.latest_target.distance:
            distance_to_target = self.latest_target.distance

        # Validate command
        is_safe, validated_command, reason = self.safety_monitor.validate_command(
            command,
            distance_to_target=distance_to_target,
            distance_to_obstacle=None
        )

        if is_safe and validated_command:
            # Send command to robot
            self._send_to_robot(validated_command)
            self.watchdog.update_command_sent()
        else:
            # Command rejected, send stop
            stop_command = SafetyVelocityCommand(0.0, 0.0, time.time())
            self._send_to_robot(stop_command)

            # Publish safety event
            msg = SafetyEventMessage(
                source_agent=self.name,
                level="critical",
                reason=f"Command rejected: {reason}",
                emergency_stop_active=self.safety_monitor.is_emergency_stop_active()
            )
            self.message_bus.publish(MessageType.SAFETY_EVENT, msg)

        # Mark command as validated
        self.latest_command.validated = True

    def _send_to_robot(self, command: SafetyVelocityCommand) -> None:
        """Send validated command to Go2 robot.

        Args:
            command: Validated velocity command
        """
        if self.go2_sdk:
            # Send to real robot via Go2 SDK
            # self.go2_sdk.send_velocity_command(command.linear_x, command.angular_z)
            pass
        else:
            # Simulation mode - just log
            self._logger.debug(
                f"[SIM] Command: linear={command.linear_x:.2f}, "
                f"angular={command.angular_z:.2f}"
            )

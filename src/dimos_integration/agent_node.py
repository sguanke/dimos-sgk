"""Dimos agent wrappers for person following system components.

This module wraps each subsystem (perception, navigation, localization, safety)
as a dimos agent that runs independently and communicates via message bus.
"""

import threading
import time
import logging
from typing import Optional
from abc import ABC, abstractmethod

from .message_handler import (
    MessageHandler,
    MessageType,
    PersonDetectionMessage,
    RobotPoseMessage,
    MotionCommandMessage,
    SafetyEventMessage,
    HealthStatusMessage,
    HeartbeatMessage,
)

logger = logging.getLogger(__name__)


class AgentState:
    """Agent lifecycle states."""
    INITIALIZED = "initialized"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


class BaseAgent(ABC):
    """Base class for all dimos agents."""

    def __init__(self, name: str, message_handler: MessageHandler):
        """Initialize base agent.

        Args:
            name: Agent name
            message_handler: Message handler for communication
        """
        self.name = name
        self.message_handler = message_handler
        self.state = AgentState.INITIALIZED
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._heartbeat_thread: Optional[threading.Thread] = None
        self.logger = logging.getLogger(f"Agent.{name}")

    @abstractmethod
    def _run_loop(self) -> None:
        """Main agent loop (implemented by subclasses)."""
        pass

    @abstractmethod
    def _initialize_components(self) -> bool:
        """Initialize agent-specific components.

        Returns:
            True if initialization successful
        """
        pass

    def start(self) -> bool:
        """Start the agent.

        Returns:
            True if started successfully
        """
        if self._running:
            self.logger.warning(f"{self.name} already running")
            return False

        try:
            # Initialize components
            if not self._initialize_components():
                self.logger.error(f"{self.name} initialization failed")
                self.state = AgentState.ERROR
                return False

            # Start agent thread
            self._running = True
            self._thread = threading.Thread(
                target=self._run_loop,
                daemon=True,
                name=f"{self.name}-thread"
            )
            self._thread.start()

            # Start heartbeat thread
            self._heartbeat_thread = threading.Thread(
                target=self._heartbeat_loop,
                daemon=True,
                name=f"{self.name}-heartbeat"
            )
            self._heartbeat_thread.start()

            self.state = AgentState.RUNNING
            self.logger.info(f"{self.name} started")
            return True

        except Exception as e:
            self.logger.error(f"{self.name} start failed: {e}")
            self.state = AgentState.ERROR
            return False

    def stop(self) -> None:
        """Stop the agent."""
        if not self._running:
            return

        self._running = False

        # Wait for threads to finish
        if self._thread:
            self._thread.join(timeout=2.0)
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=1.0)

        self.state = AgentState.STOPPED
        self.logger.info(f"{self.name} stopped")

    def _heartbeat_loop(self) -> None:
        """Send periodic heartbeat messages."""
        while self._running:
            try:
                heartbeat = HeartbeatMessage(
                    agent_name=self.name,
                    status=self.state
                )
                self.message_handler.publish(
                    MessageType.HEARTBEAT,
                    heartbeat
                )
                time.sleep(0.5)  # 2 Hz heartbeat
            except Exception as e:
                self.logger.error(f"Heartbeat error: {e}")

    def is_running(self) -> bool:
        """Check if agent is running.

        Returns:
            True if agent is running
        """
        return self._running and self.state == AgentState.RUNNING


class PerceptionAgent(BaseAgent):
    """Agent for person detection and tracking."""

    def __init__(self, message_handler: MessageHandler, config: dict):
        """Initialize perception agent.

        Args:
            message_handler: Message handler for communication
            config: Configuration dictionary
        """
        super().__init__("PerceptionAgent", message_handler)
        self.config = config
        self.detector = None
        self.tracker = None
        self.target_selector = None
        self.camera = None

    def _initialize_components(self) -> bool:
        """Initialize vision components."""
        try:
            from ..vision.person_detector import PersonDetector
            from ..vision.person_tracker import PersonTracker
            from ..vision.target_selector import TargetSelector

            vision_config = self.config.get('vision', {})

            self.detector = PersonDetector(
                model_path=vision_config.get('model_path', 'yolov8n.pt'),
                confidence_threshold=vision_config.get('confidence_threshold', 0.5),
                nms_threshold=vision_config.get('nms_threshold', 0.4)
            )

            self.tracker = PersonTracker(
                max_age=vision_config.get('max_age', 30),
                n_init=vision_config.get('n_init', 3)
            )

            self.target_selector = TargetSelector(
                fov_angle=vision_config.get('fov_angle', 60),
                max_distance=vision_config.get('max_distance', 10.0)
            )

            # TODO: Initialize camera based on mode (simulation vs hardware)
            self.logger.info("Perception components initialized")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize perception: {e}")
            return False

    def _run_loop(self) -> None:
        """Main perception loop."""
        while self._running:
            try:
                # TODO: Get frame from camera
                # frame = self.camera.get_frame()

                # For now, just sleep to simulate processing
                time.sleep(0.033)  # ~30 Hz

                # TODO: Detect persons
                # detections = self.detector.detect(frame)

                # TODO: Track persons
                # tracks = self.tracker.update(detections, frame)

                # TODO: Select target
                # target = self.target_selector.select_target(tracks)

                # TODO: Publish target if found
                # if target:
                #     msg = PersonDetectionMessage(...)
                #     self.message_handler.publish(MessageType.PERSON_DETECTION, msg)

            except Exception as e:
                self.logger.error(f"Perception loop error: {e}")
                time.sleep(0.1)


class LocalizationAgent(BaseAgent):
    """Agent for robot pose estimation and mapping."""

    def __init__(self, message_handler: MessageHandler, config: dict):
        """Initialize localization agent.

        Args:
            message_handler: Message handler for communication
            config: Configuration dictionary
        """
        super().__init__("LocalizationAgent", message_handler)
        self.config = config
        self.pose_estimator = None
        self.local_map = None

    def _initialize_components(self) -> bool:
        """Initialize localization components."""
        try:
            from ..localization.pose_estimator import PoseEstimator
            from ..mapping.local_map import LocalMap

            self.pose_estimator = PoseEstimator()
            self.local_map = LocalMap()

            self.logger.info("Localization components initialized")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize localization: {e}")
            return False

    def _run_loop(self) -> None:
        """Main localization loop."""
        while self._running:
            try:
                # TODO: Get sensor data (encoders, IMU)
                # encoder_data = ...
                # imu_data = ...

                # TODO: Update pose estimate
                # pose_estimate = self.pose_estimator.update(encoder_data, imu_data)

                # TODO: Publish pose
                # msg = RobotPoseMessage(...)
                # self.message_handler.publish(MessageType.ROBOT_POSE, msg)

                time.sleep(0.02)  # 50 Hz

            except Exception as e:
                self.logger.error(f"Localization loop error: {e}")
                time.sleep(0.1)


class NavigationAgent(BaseAgent):
    """Agent for motion control and path planning."""

    def __init__(self, message_handler: MessageHandler, config: dict):
        """Initialize navigation agent.

        Args:
            message_handler: Message handler for communication
            config: Configuration dictionary
        """
        super().__init__("NavigationAgent", message_handler)
        self.config = config
        self.motion_controller = None
        self.distance_keeper = None
        self.path_planner = None
        self.current_target: Optional[PersonDetectionMessage] = None
        self.current_pose: Optional[RobotPoseMessage] = None

    def _initialize_components(self) -> bool:
        """Initialize navigation components."""
        try:
            from ..control.motion_controller import MotionController
            from ..control.distance_keeper import DistanceKeeper
            from ..control.path_planner import PathPlanner

            robot_config = self.config.get('robot', {})

            self.motion_controller = MotionController(
                max_linear_velocity=robot_config.get('max_linear_velocity', 0.8),
                max_angular_velocity=robot_config.get('max_angular_velocity', 1.0)
            )

            self.distance_keeper = DistanceKeeper(
                target_distance=robot_config.get('target_distance', 2.0),
                distance_tolerance=robot_config.get('distance_tolerance', 0.3)
            )

            self.path_planner = PathPlanner()

            # Subscribe to messages
            self.message_handler.subscribe(
                MessageType.PERSON_DETECTION,
                self._on_person_detection
            )
            self.message_handler.subscribe(
                MessageType.ROBOT_POSE,
                self._on_robot_pose
            )

            self.logger.info("Navigation components initialized")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize navigation: {e}")
            return False

    def _on_person_detection(self, msg: PersonDetectionMessage) -> None:
        """Handle person detection message."""
        self.current_target = msg

    def _on_robot_pose(self, msg: RobotPoseMessage) -> None:
        """Handle robot pose message."""
        self.current_pose = msg

    def _run_loop(self) -> None:
        """Main navigation loop."""
        while self._running:
            try:
                if self.current_target and self.current_pose:
                    # TODO: Compute motion command
                    # cmd = self.motion_controller.compute_velocity_command(...)

                    # TODO: Publish command
                    # msg = MotionCommandMessage(...)
                    # self.message_handler.publish(MessageType.MOTION_COMMAND, msg)
                    pass

                time.sleep(0.02)  # 50 Hz

            except Exception as e:
                self.logger.error(f"Navigation loop error: {e}")
                time.sleep(0.1)


class SafetyAgent(BaseAgent):
    """Agent for safety monitoring and emergency handling."""

    def __init__(self, message_handler: MessageHandler, config: dict):
        """Initialize safety agent.

        Args:
            message_handler: Message handler for communication
            config: Configuration dictionary
        """
        super().__init__("SafetyAgent", message_handler)
        self.config = config
        self.safety_monitor = None
        self.watchdog = None
        self.health_checker = None

    def _initialize_components(self) -> bool:
        """Initialize safety components."""
        try:
            from ..safety.safety_monitor import SafetyMonitor
            from ..safety.watchdog import Watchdog
            from ..safety.health_checker import HealthChecker

            safety_config_path = self.config.get(
                'safety_config_path',
                'config/safety_params.yaml'
            )

            self.safety_monitor = SafetyMonitor(config_path=safety_config_path)
            self.watchdog = Watchdog()
            self.health_checker = HealthChecker()

            # Subscribe to motion commands for validation
            self.message_handler.subscribe(
                MessageType.MOTION_COMMAND,
                self._on_motion_command
            )

            # Subscribe to heartbeats for watchdog
            self.message_handler.subscribe(
                MessageType.HEARTBEAT,
                self._on_heartbeat
            )

            self.logger.info("Safety components initialized")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize safety: {e}")
            return False

    def _on_motion_command(self, msg: MotionCommandMessage) -> None:
        """Validate motion command."""
        try:
            # TODO: Get current distances
            target_distance = None
            obstacle_distance = None

            # Validate command
            from ..safety.safety_monitor import VelocityCommand
            cmd = VelocityCommand(
                linear_x=msg.linear_x,
                angular_z=msg.angular_z,
                timestamp=msg.timestamp
            )

            is_valid, reason = self.safety_monitor.validate_command(
                cmd,
                target_distance=target_distance,
                min_obstacle_distance=obstacle_distance
            )

            if not is_valid:
                # Publish safety event
                event_msg = SafetyEventMessage(
                    level="warning",
                    event_type="COMMAND_VETOED",
                    description=f"Command vetoed: {reason}",
                    emergency_stop_active=self.safety_monitor.is_emergency_stop_active()
                )
                self.message_handler.publish(
                    MessageType.SAFETY_EVENT,
                    event_msg
                )

        except Exception as e:
            self.logger.error(f"Motion command validation error: {e}")

    def _on_heartbeat(self, msg: HeartbeatMessage) -> None:
        """Handle heartbeat from other agents."""
        if self.watchdog:
            self.watchdog.update_heartbeat(msg.agent_name, msg.timestamp)

    def _run_loop(self) -> None:
        """Main safety monitoring loop."""
        while self._running:
            try:
                # TODO: Check watchdog timeouts
                # TODO: Check system health
                # TODO: Publish health status

                time.sleep(0.1)  # 10 Hz

            except Exception as e:
                self.logger.error(f"Safety loop error: {e}")
                time.sleep(0.1)

"""Main entry point for Go2 person following system.

This module initializes all agents, starts the dimos message bus,
and coordinates the system lifecycle.
"""

import argparse
import logging
import signal
import sys
import time
from pathlib import Path
from typing import Optional

from src.dimos_integration.agent_node import (
    PerceptionAgent,
    NavigationAgent,
    LocalizationAgent,
    SafetyAgent,
)
from src.dimos_integration.message_handler import MessageBus


# Global flag for graceful shutdown
shutdown_requested = False


def setup_logging(debug: bool = False) -> None:
    """Setup logging configuration.

    Args:
        debug: Enable debug logging
    """
    log_level = logging.DEBUG if debug else logging.INFO

    # Create logs directory
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(
                log_dir / f"go2_person_following_{time.strftime('%Y%m%d_%H%M%S')}.log"
            )
        ]
    )

    logger = logging.getLogger(__name__)
    logger.info("Logging initialized")


def signal_handler(signum, frame):
    """Handle shutdown signals (Ctrl+C)."""
    global shutdown_requested
    logger = logging.getLogger(__name__)
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_requested = True


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Go2 Robot Person Following System"
    )

    parser.add_argument(
        "--mode",
        type=str,
        choices=["simulation", "hardware"],
        default="simulation",
        help="Operation mode: simulation (no hardware) or hardware (requires Go2)"
    )

    parser.add_argument(
        "--robot-ip",
        type=str,
        default="192.168.123.161",
        help="Go2 robot IP address (for hardware mode)"
    )

    parser.add_argument(
        "--camera",
        type=int,
        default=0,
        help="Camera device index (0 for default camera)"
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )

    parser.add_argument(
        "--visualize",
        action="store_true",
        help="Show camera feed with detections"
    )

    parser.add_argument(
        "--config-dir",
        type=str,
        default="config",
        help="Configuration directory path"
    )

    return parser.parse_args()


def load_go2_sdk(robot_ip: str):
    """Load and initialize Go2 SDK.

    Args:
        robot_ip: Robot IP address

    Returns:
        Initialized Go2 SDK instance or None if failed
    """
    logger = logging.getLogger(__name__)

    try:
        # Import Go2 SDK (placeholder - actual import depends on SDK)
        # from unitree_go2_sdk import Go2SDK
        # sdk = Go2SDK(robot_ip)
        # sdk.connect()
        # logger.info(f"Connected to Go2 robot at {robot_ip}")
        # return sdk

        logger.warning("Go2 SDK not available, running in simulation mode")
        return None

    except Exception as e:
        logger.error(f"Failed to initialize Go2 SDK: {e}")
        return None


def main():
    """Main entry point."""
    global shutdown_requested

    # Parse arguments
    args = parse_arguments()

    # Setup logging
    setup_logging(args.debug)
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("Go2 Person Following System")
    logger.info("=" * 60)
    logger.info(f"Mode: {args.mode}")
    logger.info(f"Camera: {args.camera}")
    logger.info(f"Debug: {args.debug}")
    logger.info(f"Visualize: {args.visualize}")
    logger.info("=" * 60)

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Initialize Go2 SDK if in hardware mode
    go2_sdk = None
    if args.mode == "hardware":
        logger.info(f"Initializing Go2 SDK for robot at {args.robot_ip}")
        go2_sdk = load_go2_sdk(args.robot_ip)
        if go2_sdk is None:
            logger.warning("Failed to connect to Go2, falling back to simulation mode")
            args.mode = "simulation"

    # Initialize message bus
    logger.info("Initializing message bus...")
    message_bus = MessageBus()

    # Initialize agents in correct order
    agents = []

    try:
        # 1. LocalizationAgent (provides pose estimates)
        logger.info("Initializing LocalizationAgent...")
        localization_agent = LocalizationAgent(
            message_bus=message_bus,
            update_rate=50.0,
            go2_sdk=go2_sdk
        )
        agents.append(localization_agent)

        # 2. PerceptionAgent (detects and tracks persons)
        logger.info("Initializing PerceptionAgent...")
        perception_agent = PerceptionAgent(
            message_bus=message_bus,
            camera_source=args.camera,
            update_rate=30.0
        )
        agents.append(perception_agent)

        # 3. SafetyAgent (monitors and validates commands)
        logger.info("Initializing SafetyAgent...")
        safety_agent = SafetyAgent(
            message_bus=message_bus,
            update_rate=50.0,
            config_path=f"{args.config_dir}/safety_params.yaml",
            go2_sdk=go2_sdk
        )
        agents.append(safety_agent)

        # 4. NavigationAgent (computes motion commands)
        logger.info("Initializing NavigationAgent...")
        navigation_agent = NavigationAgent(
            message_bus=message_bus,
            update_rate=50.0,
            config_path=f"{args.config_dir}/robot_params.yaml"
        )
        agents.append(navigation_agent)

        logger.info("All agents initialized successfully")

        # Start all agents
        logger.info("Starting agents...")
        for agent in agents:
            agent.start()
            time.sleep(0.1)  # Small delay between starts

        logger.info("All agents started successfully")
        logger.info("System is running. Press Ctrl+C to stop.")

        # Main loop - just keep running until shutdown
        while not shutdown_requested:
            time.sleep(0.5)

            # Print status periodically
            if args.debug:
                stats = message_bus.get_stats()
                logger.debug(f"Message bus stats: {stats}")

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        shutdown_requested = True

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        shutdown_requested = True

    finally:
        # Graceful shutdown
        logger.info("Shutting down agents...")

        # Stop agents in reverse order
        for agent in reversed(agents):
            try:
                logger.info(f"Stopping {agent.name}...")
                agent.stop()
            except Exception as e:
                logger.error(f"Error stopping {agent.name}: {e}")

        # Disconnect Go2 SDK
        if go2_sdk:
            try:
                logger.info("Disconnecting from Go2 robot...")
                # go2_sdk.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting Go2 SDK: {e}")

        logger.info("Shutdown complete")
        logger.info("=" * 60)


if __name__ == "__main__":
    main()

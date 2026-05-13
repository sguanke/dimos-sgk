"""Main entry point for Go2 person following system.

This module initializes all agents, starts the dimos message bus,
and coordinates the person following system.
"""

import argparse
import logging
import signal
import sys
import time
from pathlib import Path
from typing import Optional

import yaml

from dimos_integration import (
    MessageHandler,
    PerceptionAgent,
    NavigationAgent,
    LocalizationAgent,
    SafetyAgent,
)


class PersonFollowingSystem:
    """Main system coordinator for person following."""

    def __init__(self, config: dict, args: argparse.Namespace):
        """Initialize the person following system.

        Args:
            config: Configuration dictionary
            args: Command-line arguments
        """
        self.config = config
        self.args = args
        self.logger = self._setup_logging()
        self.message_handler: Optional[MessageHandler] = None
        self.agents = []
        self._shutdown_requested = False

        # Register signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration.

        Returns:
            Logger instance
        """
        log_level = logging.DEBUG if self.args.debug else logging.INFO

        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler('logs/system.log')
            ]
        )

        # Create logs directory
        Path('logs').mkdir(exist_ok=True)

        return logging.getLogger('PersonFollowingSystem')

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals.

        Args:
            signum: Signal number
            frame: Current stack frame
        """
        self.logger.info(f"Received signal {signum}, shutting down...")
        self._shutdown_requested = True

    def _load_configurations(self) -> dict:
        """Load all configuration files.

        Returns:
            Merged configuration dictionary
        """
        config_files = [
            'config/robot_params.yaml',
            'config/vision_params.yaml',
            'config/safety_params.yaml'
        ]

        merged_config = {}

        for config_file in config_files:
            try:
                with open(config_file, 'r') as f:
                    file_config = yaml.safe_load(f)
                    merged_config.update(file_config)
                    self.logger.info(f"Loaded config: {config_file}")
            except FileNotFoundError:
                self.logger.warning(f"Config file not found: {config_file}")
            except Exception as e:
                self.logger.error(f"Error loading {config_file}: {e}")

        return merged_config

    def initialize(self) -> bool:
        """Initialize all system components.

        Returns:
            True if initialization successful
        """
        try:
            self.logger.info("Initializing person following system...")
            self.logger.info(f"Mode: {self.args.mode}")
            if self.args.mode == 'hardware':
                self.logger.info(f"Robot IP: {self.args.robot_ip}")

            # Load configurations
            full_config = self._load_configurations()
            full_config.update(self.config)

            # Initialize message handler
            self.message_handler = MessageHandler()
            self.message_handler.start()
            self.logger.info("Message handler started")

            # Initialize agents in correct order
            # 1. LocalizationAgent (provides pose to others)
            localization_agent = LocalizationAgent(
                self.message_handler,
                full_config
            )
            self.agents.append(localization_agent)

            # 2. PerceptionAgent (detects target)
            perception_agent = PerceptionAgent(
                self.message_handler,
                full_config
            )
            self.agents.append(perception_agent)

            # 3. SafetyAgent (monitors everything)
            safety_agent = SafetyAgent(
                self.message_handler,
                full_config
            )
            self.agents.append(safety_agent)

            # 4. NavigationAgent (controls motion)
            navigation_agent = NavigationAgent(
                self.message_handler,
                full_config
            )
            self.agents.append(navigation_agent)

            self.logger.info("All agents initialized")
            return True

        except Exception as e:
            self.logger.error(f"Initialization failed: {e}", exc_info=True)
            return False

    def start(self) -> bool:
        """Start all agents.

        Returns:
            True if all agents started successfully
        """
        try:
            self.logger.info("Starting all agents...")

            for agent in self.agents:
                if not agent.start():
                    self.logger.error(f"Failed to start {agent.name}")
                    return False
                time.sleep(0.1)  # Small delay between agent starts

            self.logger.info("All agents started successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to start agents: {e}", exc_info=True)
            return False

    def run(self) -> None:
        """Run the main system loop."""
        self.logger.info("Person following system running")
        self.logger.info("Press Ctrl+C to stop")

        try:
            while not self._shutdown_requested:
                # Main loop - just monitor agents
                time.sleep(1.0)

                # Check if all agents are still running
                for agent in self.agents:
                    if not agent.is_running():
                        self.logger.warning(
                            f"{agent.name} is not running (state: {agent.state})"
                        )

                # Print statistics periodically
                if int(time.time()) % 10 == 0:
                    self._print_statistics()

        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received")
        except Exception as e:
            self.logger.error(f"Error in main loop: {e}", exc_info=True)

    def _print_statistics(self) -> None:
        """Print system statistics."""
        if self.message_handler:
            stats = self.message_handler.get_statistics()
            self.logger.info("=== Message Statistics ===")
            for msg_type, data in stats.items():
                if data['published'] > 0:
                    self.logger.info(
                        f"  {msg_type}: published={data['published']}, "
                        f"delivered={data['delivered']}, "
                        f"queue={data['queue_size']}, "
                        f"subscribers={data['subscribers']}"
                    )

    def shutdown(self) -> None:
        """Shutdown all system components."""
        self.logger.info("Shutting down person following system...")

        # Stop agents in reverse order
        for agent in reversed(self.agents):
            try:
                agent.stop()
                self.logger.info(f"{agent.name} stopped")
            except Exception as e:
                self.logger.error(f"Error stopping {agent.name}: {e}")

        # Stop message handler
        if self.message_handler:
            self.message_handler.stop()
            self.logger.info("Message handler stopped")

        self.logger.info("Shutdown complete")


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description='Go2 Robot Person Following System'
    )

    parser.add_argument(
        '--mode',
        type=str,
        choices=['simulation', 'hardware'],
        default='simulation',
        help='Operating mode (default: simulation)'
    )

    parser.add_argument(
        '--robot-ip',
        type=str,
        default='192.168.123.161',
        help='Go2 robot IP address (default: 192.168.123.161)'
    )

    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )

    parser.add_argument(
        '--visualize',
        action='store_true',
        help='Show camera feed with detections'
    )

    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_arguments()

    # Create system configuration
    config = {
        'mode': args.mode,
        'robot_ip': args.robot_ip,
        'visualize': args.visualize,
    }

    # Create and initialize system
    system = PersonFollowingSystem(config, args)

    if not system.initialize():
        print("Failed to initialize system", file=sys.stderr)
        sys.exit(1)

    # Start system
    if not system.start():
        print("Failed to start system", file=sys.stderr)
        system.shutdown()
        sys.exit(1)

    # Run main loop
    try:
        system.run()
    finally:
        system.shutdown()


if __name__ == '__main__':
    main()

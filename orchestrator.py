#!/usr/bin/env python3
"""
Multi-agent orchestrator for Go2 person following project.
Executes the workflow defined in .claude/workflow.yml
"""

import subprocess
import json
import yaml
from pathlib import Path
from typing import Dict, List, Optional
import sys
import time
import logging
from datetime import datetime


class AgentOrchestrator:
    def __init__(self, workflow_path: str = ".claude/workflow.yml"):
        self.workflow_path = Path(workflow_path)
        self.workflow = self.load_workflow()
        self.state_dir = Path(self.workflow["project"]["state_dir"])
        self.worktree_dir = Path(self.workflow["project"]["worktree_dir"])
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.worktree_dir.mkdir(parents=True, exist_ok=True)
        self.completed_phases = set()

        # Setup logging
        self.setup_logging()

    def setup_logging(self):
        """Setup logging to both console and file"""
        log_dir = Path(".claude/logs")
        log_dir.mkdir(parents=True, exist_ok=True)

        # Create log file with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"orchestrator_{timestamp}.log"

        # Configure logging
        self.logger = logging.getLogger("orchestrator")
        self.logger.setLevel(logging.INFO)

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter('%(message)s')
        console_handler.setFormatter(console_format)

        # File handler
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_format)

        # Add handlers
        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)

        self.logger.info(f"Logging to: {log_file}")
        self.logger.info("="*60)

    def log(self, message: str, level: str = "info"):
        """Log message to both console and file"""
        if level == "info":
            self.logger.info(message)
        elif level == "warning":
            self.logger.warning(message)
        elif level == "error":
            self.logger.error(message)
        elif level == "debug":
            self.logger.debug(message)

    def load_workflow(self) -> Dict:
        """Load workflow configuration from YAML"""
        with open(self.workflow_path) as f:
            return yaml.safe_load(f)

    def save_state(self, phase_name: str, data: Dict):
        """Save phase execution state"""
        state_file = self.state_dir / f"{phase_name}_state.json"
        with open(state_file, 'w') as f:
            json.dump({
                "phase": phase_name,
                "timestamp": time.time(),
                "data": data
            }, f, indent=2)
        self.log(f"State saved: {state_file}", "debug")

    def load_state(self, phase_name: str) -> Optional[Dict]:
        """Load phase execution state"""
        state_file = self.state_dir / f"{phase_name}_state.json"
        if state_file.exists():
            with open(state_file) as f:
                return json.load(f)
        return None

    def git_commit_and_push(self, agent_config: Dict) -> bool:
        """Commit and push code to remote after agent completes"""
        if not agent_config.get("auto_commit", False):
            return True

        agent_name = agent_config["name"]
        commit_message = agent_config.get("commit_message", f"Update from {agent_name}")

        self.log(f"\n{'─'*60}")
        self.log(f"📤 Committing and pushing code for {agent_name}")
        self.log(f"{'─'*60}")

        try:
            # Get current branch name
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True,
                text=True,
                timeout=30,
                check=True
            )
            current_branch = result.stdout.strip()

            if not current_branch:
                self.log("  ⚠️  Not on any branch (detached HEAD), skipping push", "warning")
                return True

            self.log(f"  📍 Current branch: {current_branch}")

            # Check if there are changes to commit
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                timeout=30
            )

            if not result.stdout.strip():
                self.log("  ℹ️  No changes to commit", "warning")
                return True

            self.log(f"  📝 Changes detected:\n{result.stdout}")

            # Add all changes
            self.log("  ➕ Adding changes to git...")
            subprocess.run(
                ["git", "add", "-A"],
                check=True,
                timeout=30
            )

            # Commit
            self.log(f"  💾 Creating commit: {commit_message}")
            full_commit_msg = f"{commit_message}\n\nCo-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
            subprocess.run(
                ["git", "commit", "-m", full_commit_msg],
                check=True,
                timeout=30
            )

            # Push to remote (current branch)
            self.log(f"  🚀 Pushing to origin/{current_branch}")
            subprocess.run(
                ["git", "push", "-u", "origin", current_branch],
                check=True,
                timeout=120
            )

            self.log(f"  ✅ Successfully pushed to origin/{current_branch}")
            return True

        except subprocess.CalledProcessError as e:
            self.log(f"  ❌ Git operation failed: {e}", "error")
            return False
        except subprocess.TimeoutExpired:
            self.log(f"  ❌ Git operation timed out", "error")
            return False
        except Exception as e:
            self.log(f"  ❌ Unexpected error: {e}", "error")
            return False

    def build_claude_cmd(self, prompt: str, output_file: Optional[str] = None) -> List[str]:
        """Build Claude Code command"""
        cmd = ["claude"]
        cmd.extend(["--prompt", prompt])
        return cmd

    def check_dependencies(self, phase: Dict) -> bool:
        """Check if all dependencies for a phase are completed"""
        dependencies = phase.get("dependencies", [])
        for dep in dependencies:
            if dep not in self.completed_phases:
                self.log(f"  ⏳ Waiting for dependency: {dep}", "warning")
                return False
        return True

    def check_agent_condition(self, agent_config: Dict, context: Dict) -> bool:
        """Check if agent's execution condition is met"""
        condition = agent_config.get("condition")
        if not condition:
            return True

        # Parse condition expression
        # Example: "test_results.failed > 0"
        try:
            # Simple evaluation - can be enhanced with safer eval
            # For now, check common patterns
            if "test_results.failed > 0" in condition:
                test_results_file = self.state_dir / "test_results.json"
                if test_results_file.exists():
                    with open(test_results_file) as f:
                        data = json.load(f)
                        return data.get("failed", 0) > 0
                return False

            if "problem_analysis.problems.length > 0" in condition:
                analysis_file = self.state_dir / "problem_analysis.json"
                if analysis_file.exists():
                    with open(analysis_file) as f:
                        data = json.load(f)
                        return len(data.get("problems", [])) > 0
                return False

            # Default: condition not recognized, run agent
            return True
        except Exception as e:
            self.log(f"  ⚠️  Error evaluating condition: {e}", "warning")
            return True

    def load_context(self) -> Dict:
        """Load execution context from state files"""
        context = {}

        # Load test results if available
        test_results_file = self.state_dir / "test_results.json"
        if test_results_file.exists():
            with open(test_results_file) as f:
                context["test_results"] = json.load(f)

        # Load problem analysis if available
        analysis_file = self.state_dir / "problem_analysis.json"
        if analysis_file.exists():
            with open(analysis_file) as f:
                context["problem_analysis"] = json.load(f)

        return context

    def validate_agent_output(self, agent_name: str, expected_files: List[str]) -> bool:
        """Validate that agent created expected files"""
        missing_files = []
        for file_path in expected_files:
            if not Path(file_path).exists():
                missing_files.append(file_path)

        if missing_files:
            self.log(f"  ⚠️  Agent {agent_name} did not create expected files:", "warning")
            for f in missing_files:
                self.log(f"     - {f}", "warning")
            return False
        return True

    def run_agent(self, agent_config: Dict, retry_count: int = 0, context: Optional[Dict] = None) -> bool:
        """Run a single agent"""
        agent_name = agent_config.get("name", "unnamed")

        # Check if agent should run based on condition
        if context is None:
            context = self.load_context()

        if not self.check_agent_condition(agent_config, context):
            self.log(f"\n⏭️  Skipping agent {agent_name} (condition not met)")
            return True  # Not an error, just skipped

        self.log(f"\n{'='*60}")
        self.log(f"🤖 Running agent: {agent_name}")
        self.log(f"{'='*60}")
        self.log(f"Retry count: {retry_count}")
        self.log(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        prompt = agent_config["prompt"].strip()
        output_file = agent_config.get("output")

        # Log agent configuration
        self.log(f"\n📋 Agent Configuration:")
        self.log(f"  - Name: {agent_name}")
        self.log(f"  - Output: {output_file}")
        self.log(f"  - Auto-commit: {agent_config.get('auto_commit', False)}")
        if agent_config.get('auto_commit'):
            self.log(f"  - Push branch: {agent_config.get('push_branch', 'N/A')}")
        self.log(f"  - Prompt length: {len(prompt)} chars")

        # Build command
        cmd = self.build_claude_cmd(prompt, output_file)

        self.log(f"\n▶️  Executing agent...")
        start_time = time.time()

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout
            )

            elapsed_time = time.time() - start_time

            # Save output
            output_data = {
                "agent_name": agent_name,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "retry_count": retry_count,
                "timestamp": time.time(),
                "elapsed_seconds": elapsed_time
            }

            if output_file:
                output_path = Path(output_file)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, 'w') as f:
                    json.dump(output_data, f, indent=2)

            self.log(f"\n⏱️  Execution time: {elapsed_time:.2f} seconds")

            if result.returncode == 0:
                self.log(f"✅ Agent {agent_name} completed successfully")

                # Log output summary
                if result.stdout:
                    stdout_lines = result.stdout.strip().split('\n')
                    self.log(f"\n📄 Output summary (first 10 lines):")
                    for line in stdout_lines[:10]:
                        self.log(f"  {line}")
                    if len(stdout_lines) > 10:
                        self.log(f"  ... ({len(stdout_lines) - 10} more lines)")

                if output_file and Path(output_file).exists():
                    self.log(f"  ✓ Output file created: {output_file}")

                # Commit and push if configured
                if agent_config.get("auto_commit", False):
                    if not self.git_commit_and_push(agent_config):
                        self.log(f"  ⚠️  Git push failed, but agent completed", "warning")

                return True
            else:
                self.log(f"❌ Agent {agent_name} failed with code {result.returncode}", "error")
                if result.stderr:
                    self.log(f"\n🔴 Error output:", "error")
                    for line in result.stderr[:500].split('\n'):
                        self.log(f"  {line}", "error")
                return False

        except subprocess.TimeoutExpired:
            self.log(f"❌ Agent {agent_name} timed out after 1 hour", "error")
            return False
        except Exception as e:
            self.log(f"❌ Agent {agent_name} failed with exception: {e}", "error")
            return False

    def run_phase(self, phase: Dict, retry_count: int = 0) -> bool:
        """Run a single phase (may contain multiple agents)"""
        phase_name = phase["name"]

        self.log(f"\n{'#'*60}")
        self.log(f"# PHASE: {phase_name}")
        self.log(f"{'#'*60}")
        self.log(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Check dependencies
        if not self.check_dependencies(phase):
            self.log(f"❌ Phase {phase_name} dependencies not met", "error")
            return False

        # Check if this phase has a loop configuration
        loop_config = phase.get("loop", {})
        if loop_config:
            return self.run_phase_with_loop(phase, loop_config, retry_count)

        phase_start_time = time.time()

        # Check if this is a multi-agent phase
        if "agents" in phase:
            agents = phase["agents"]
            parallel = phase.get("parallel", False)

            self.log(f"\n📊 Phase contains {len(agents)} agents")
            self.log(f"Execution mode: {'Parallel' if parallel else 'Sequential'}")

            context = self.load_context()

            if parallel:
                self.log(f"\n⚡ Running {len(agents)} agents in parallel...")
                # For now, run sequentially (true parallel would need multiprocessing)
                results = []
                for i, agent in enumerate(agents, 1):
                    self.log(f"\n[{i}/{len(agents)}] Starting agent: {agent['name']}")
                    success = self.run_agent(agent, retry_count, context)
                    results.append((agent["name"], success))

                # Check if all succeeded
                all_success = all(success for _, success in results)

                self.log(f"\n{'─'*60}")
                self.log(f"📊 Parallel phase results:")
                for name, success in results:
                    status = "✅" if success else "❌"
                    self.log(f"  {status} {name}")
                self.log(f"{'─'*60}")

                phase_elapsed = time.time() - phase_start_time
                self.log(f"\n⏱️  Phase total time: {phase_elapsed:.2f} seconds")

                return all_success
            else:
                # Run agents sequentially
                for i, agent in enumerate(agents, 1):
                    self.log(f"\n[{i}/{len(agents)}] Starting agent: {agent['name']}")
                    if not self.run_agent(agent, retry_count, context):
                        return False
                    # Reload context after each agent
                    context = self.load_context()

                phase_elapsed = time.time() - phase_start_time
                self.log(f"\n⏱️  Phase total time: {phase_elapsed:.2f} seconds")
                return True
        else:
            # Single agent phase (use phase config as agent config)
            context = self.load_context()
            success = self.run_agent(phase, retry_count, context)
            phase_elapsed = time.time() - phase_start_time
            self.log(f"\n⏱️  Phase total time: {phase_elapsed:.2f} seconds")
            return success

    def run_phase_with_loop(self, phase: Dict, loop_config: Dict, retry_count: int = 0) -> bool:
        """Run a phase with loop configuration (for test-fix cycles)"""
        phase_name = phase["name"]
        max_iterations = loop_config.get("max_iterations", 1)
        break_on_success = loop_config.get("break_on_success", False)

        self.log(f"\n🔄 Phase has loop configuration:")
        self.log(f"  - Max iterations: {max_iterations}")
        self.log(f"  - Break on success: {break_on_success}")

        for iteration in range(max_iterations):
            self.log(f"\n{'─'*60}")
            self.log(f"🔄 Loop iteration {iteration + 1}/{max_iterations}")
            self.log(f"{'─'*60}")

            phase_start_time = time.time()

            # Run all agents in the phase
            agents = phase.get("agents", [])
            context = self.load_context()

            all_success = True
            for i, agent in enumerate(agents, 1):
                self.log(f"\n[{i}/{len(agents)}] Starting agent: {agent['name']}")
                success = self.run_agent(agent, retry_count, context)
                if not success:
                    all_success = False
                    break
                # Reload context after each agent
                context = self.load_context()

            phase_elapsed = time.time() - phase_start_time
            self.log(f"\n⏱️  Iteration time: {phase_elapsed:.2f} seconds")

            if not all_success:
                self.log(f"❌ Iteration {iteration + 1} failed", "error")
                return False

            # Check success condition
            if break_on_success and self.check_loop_success_condition(context):
                self.log(f"\n✅ Success condition met after {iteration + 1} iteration(s)")
                self.log(f"Breaking loop early")
                return True

        self.log(f"\n⏱️  Total loop time: {phase_elapsed:.2f} seconds")
        return True

    def check_loop_success_condition(self, context: Dict) -> bool:
        """Check if loop should break (e.g., all tests passed)"""
        # Check if all tests passed
        test_results = context.get("test_results", {})
        if test_results:
            failed = test_results.get("failed", 0)
            if failed == 0:
                self.log(f"  ✅ All tests passed (0 failures)")
                return True
            else:
                self.log(f"  ⚠️  Still have {failed} failing test(s)")
                return False

        # If no test results, assume success
        return False

    def execute(self) -> bool:
        """Execute the entire workflow"""
        project = self.workflow["project"]
        phases = project["phases"]
        error_config = project.get("error_handling", {})
        max_retries = error_config.get("max_retries", 0)

        self.log(f"\n{'='*60}")
        self.log(f"🚀 Starting workflow: {project['name']}")
        self.log(f"{'='*60}")
        self.log(f"Description: {project['description']}")
        self.log(f"Total phases: {len(phases)}")
        self.log(f"Max retries per phase: {max_retries}")
        self.log(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.log(f"{'='*60}\n")

        workflow_start_time = time.time()

        for phase_idx, phase in enumerate(phases, 1):
            phase_name = phase["name"]

            self.log(f"\n{'█'*60}")
            self.log(f"█ Phase {phase_idx}/{len(phases)}: {phase_name}")
            self.log(f"{'█'*60}")

            # Try to run phase with retries
            success = False
            for attempt in range(max_retries + 1):
                if attempt > 0:
                    self.log(f"\n🔄 Retrying phase {phase_name} (attempt {attempt + 1}/{max_retries + 1})")
                    time.sleep(2)

                success = self.run_phase(phase, attempt)

                if success:
                    break

            if not success:
                self.log(f"\n{'='*60}", "error")
                self.log(f"❌ Phase {phase_name} failed after {max_retries + 1} attempts", "error")
                self.log(f"{'='*60}", "error")
                self.save_state("failed", {
                    "phase": phase_name,
                    "reason": "max_retries_exceeded",
                    "completed_phases": list(self.completed_phases)
                })
                return False

            # Mark phase as completed
            self.completed_phases.add(phase_name)
            self.save_state(phase_name, {"status": "completed"})
            self.log(f"\n✅ Phase {phase_name} completed successfully")

        workflow_elapsed = time.time() - workflow_start_time

        self.log(f"\n{'='*60}")
        self.log(f"🎉 Workflow completed successfully!")
        self.log(f"{'='*60}")
        self.log(f"\n📊 Summary:")
        self.log(f"  Total phases: {len(phases)}")
        self.log(f"  Completed: {len(self.completed_phases)}")
        self.log(f"  Total time: {workflow_elapsed:.2f} seconds ({workflow_elapsed/60:.2f} minutes)")
        self.log(f"  State saved in: {self.state_dir}")
        self.log(f"  End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.log(f"{'='*60}\n")

        return True


def main():
    """Main entry point"""
    workflow_file = ".claude/workflow.yml"

    if not Path(workflow_file).exists():
        print(f"Error: Workflow file not found: {workflow_file}")
        print(f"Current directory: {Path.cwd()}")
        sys.exit(1)

    print("=" * 60)
    print("Multi-Agent Orchestrator for Go2 Person Following")
    print("=" * 60)
    print()

    orchestrator = AgentOrchestrator(workflow_file)
    success = orchestrator.execute()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Validate workflow.yml configuration for correctness and consistency.
"""

import yaml
import json
from pathlib import Path
from typing import Dict, List, Set


class WorkflowValidator:
    def __init__(self, workflow_path: str = ".claude/workflow.yml"):
        self.workflow_path = Path(workflow_path)
        self.errors = []
        self.warnings = []

    def validate(self) -> bool:
        """Run all validation checks"""
        print(f"Validating {self.workflow_path}...")

        # Load workflow
        try:
            with open(self.workflow_path) as f:
                self.workflow = yaml.safe_load(f)
        except Exception as e:
            self.errors.append(f"Failed to load YAML: {e}")
            return False

        # Run validation checks
        self.check_structure()
        self.check_phase_dependencies()
        self.check_agent_consistency()
        self.check_output_paths()
        self.check_conditions()
        self.check_file_references()

        # Print results
        self.print_results()

        return len(self.errors) == 0

    def check_structure(self):
        """Check basic structure"""
        if "project" not in self.workflow:
            self.errors.append("Missing 'project' key")
            return

        project = self.workflow["project"]
        required_keys = ["name", "phases", "state_dir"]
        for key in required_keys:
            if key not in project:
                self.errors.append(f"Missing required key: project.{key}")

    def check_phase_dependencies(self):
        """Check phase dependencies are valid"""
        phases = self.workflow.get("project", {}).get("phases", [])
        phase_names = {phase["name"] for phase in phases}

        for phase in phases:
            deps = phase.get("dependencies", [])
            for dep in deps:
                if dep not in phase_names:
                    self.errors.append(
                        f"Phase '{phase['name']}' depends on unknown phase '{dep}'"
                    )

    def check_agent_consistency(self):
        """Check agent names and configurations"""
        phases = self.workflow.get("project", {}).get("phases", [])

        for phase in phases:
            phase_name = phase["name"]

            # Check multi-agent phases
            if "agents" in phase:
                agent_names = set()
                for agent in phase["agents"]:
                    name = agent.get("name")
                    if not name:
                        self.errors.append(f"Agent in phase '{phase_name}' missing name")
                        continue

                    # Check for duplicate names in same phase
                    if name in agent_names:
                        self.warnings.append(
                            f"Duplicate agent name '{name}' in phase '{phase_name}'"
                        )
                    agent_names.add(name)

                    # Check agent has prompt
                    if "prompt" not in agent:
                        self.errors.append(
                            f"Agent '{name}' in phase '{phase_name}' missing prompt"
                        )

                    # Check agent dependencies
                    agent_deps = agent.get("dependencies", [])
                    for dep in agent_deps:
                        if dep not in agent_names and dep != phase_name:
                            # Check if it's a previous agent in same phase
                            found = False
                            for prev_agent in phase["agents"]:
                                if prev_agent["name"] == dep:
                                    found = True
                                    break
                            if not found:
                                self.warnings.append(
                                    f"Agent '{name}' depends on '{dep}' which may not exist yet"
                                )

    def check_output_paths(self):
        """Check output paths are consistent"""
        phases = self.workflow.get("project", {}).get("phases", [])
        state_dir = self.workflow.get("project", {}).get("state_dir", ".claude/state")

        for phase in phases:
            # Check phase output
            if "output" in phase:
                output = phase["output"]
                if not output.startswith(".claude/"):
                    self.warnings.append(
                        f"Phase '{phase['name']}' output not in .claude/ directory: {output}"
                    )

            # Check agent outputs
            if "agents" in phase:
                for agent in phase["agents"]:
                    if "output" in agent:
                        output = agent["output"]
                        if not output.startswith(".claude/"):
                            self.warnings.append(
                                f"Agent '{agent['name']}' output not in .claude/ directory: {output}"
                            )

    def check_conditions(self):
        """Check condition expressions are supported"""
        supported_patterns = [
            "test_results.failed > 0",
            "problem_analysis.problems.length > 0",
            "exists and not empty"
        ]

        phases = self.workflow.get("project", {}).get("phases", [])

        for phase in phases:
            if "agents" in phase:
                for agent in phase["agents"]:
                    condition = agent.get("condition")
                    if condition:
                        supported = any(pattern in condition for pattern in supported_patterns)
                        if not supported:
                            self.warnings.append(
                                f"Agent '{agent['name']}' has unsupported condition: {condition}"
                            )

    def check_file_references(self):
        """Check file references in prompts match output fields"""
        phases = self.workflow.get("project", {}).get("phases", [])

        # Collect all output files
        output_files = set()
        for phase in phases:
            if "output" in phase:
                output_files.add(Path(phase["output"]).name)
            if "agents" in phase:
                for agent in phase["agents"]:
                    if "output" in agent:
                        output_files.add(Path(agent["output"]).name)

        # Check prompts reference existing files
        for phase in phases:
            if "agents" in phase:
                for agent in phase["agents"]:
                    prompt = agent.get("prompt", "")

                    # Look for file references in prompt
                    import re
                    file_refs = re.findall(r'\.claude/state/(\w+\.json)', prompt)
                    for file_ref in file_refs:
                        if file_ref not in output_files:
                            self.warnings.append(
                                f"Agent '{agent['name']}' references '{file_ref}' which is not in any output"
                            )

    def print_results(self):
        """Print validation results"""
        print("\n" + "="*60)

        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)}):")
            for error in self.errors:
                print(f"  - {error}")

        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  - {warning}")

        if not self.errors and not self.warnings:
            print("\n✅ All checks passed!")
        elif not self.errors:
            print(f"\n✅ No errors found ({len(self.warnings)} warnings)")

        print("="*60 + "\n")


if __name__ == "__main__":
    import sys

    validator = WorkflowValidator()
    success = validator.validate()

    sys.exit(0 if success else 1)

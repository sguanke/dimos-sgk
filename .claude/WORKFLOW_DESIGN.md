# Workflow Configuration Design

This document describes the design decisions and structure of the multi-agent workflow configuration.

## Overview

The workflow orchestrates multiple Claude Code agents to implement a person-following robot system with automatic test-fix loops.

## Workflow Phases

### 1. Planning Phase
- **Agent**: planning-agent
- **Purpose**: Create implementation plan
- **Output**: `.claude/plan.md`
- **Duration**: ~10 minutes

### 2. Implementation Phase (Parallel)
- **Agents**: 4 module agents running in parallel
  - perception-agent: Vision detection and tracking
  - navigation-agent: Motion control and path planning
  - localization-agent: Odometry, IMU fusion, mapping
  - safety-agent: Monitoring, watchdog, health checks
- **Isolation**: Each agent works on separate modules
- **Auto-commit**: Each agent commits its implementation
- **Duration**: ~20-30 minutes

### 3. Integration Phase
- **Agent**: integration-agent
- **Purpose**: Integrate all modules with dimos framework
- **Dependencies**: All implementation agents
- **Duration**: ~10-15 minutes

### 4. Testing Phase (Parallel)
- **Agents**: 3 test agents running in parallel
  - unit-test-agent: Unit tests for all modules
  - integration-test-agent: Module interaction tests
  - simulation-test-agent: End-to-end scenarios
- **Output**: Test files in `tests/` directory
- **Duration**: ~40-50 minutes

### 5. Auto-Test-and-Fix Phase (Loop)
- **Loop Configuration**:
  - max_iterations: 6
  - break_on_success: true (breaks when all tests pass)
- **Agents** (sequential in each iteration):
  1. test-runner-agent: Run pytest and collect results
  2. debugger-agent: Analyze failures and classify by module
  3. Module fixers (conditional, based on failures):
     - perception-agent: Fix perception module failures
     - navigation-agent: Fix navigation module failures
     - localization-agent: Fix localization module failures
     - safety-agent: Fix safety module failures
     - integration-agent: Fix integration module failures
- **Condition Pattern**: `{module}_failures.json exists and not empty`
- **Duration**: Variable (depends on test failures)

### 6. Review Phase
- **Agent**: review-agent
- **Purpose**: Code review and quality check
- **Output**: `.claude/state/review.md`
- **Duration**: ~10-15 minutes

### 7. Final Integration Phase
- **Agent**: final-integration-agent
- **Purpose**: Final verification and documentation
- **Duration**: ~10-15 minutes

## Key Design Decisions

### Why Module-Specific Fixers?
Instead of a single fixer-agent, we reuse the original implementation agents to fix their own modules:
- **Context preservation**: Each agent has full context of its module
- **Expertise**: The agent that wrote the code knows it best
- **Parallel potential**: Different modules can be fixed independently

### Why Conditional Execution?
Module fixers use conditions like `perception_failures.json exists and not empty`:
- **Efficiency**: Only run fixers for modules with actual failures
- **Resource optimization**: Don't waste time on modules that pass tests
- **Clear responsibility**: Each fixer knows exactly what to fix

### Why Auto-Commit?
Each agent commits its changes with descriptive messages:
- **Traceability**: Clear git history of what each agent did
- **Rollback capability**: Easy to revert specific agent's changes
- **Clean state**: Next agent starts with a clean working directory

### Why Loop with Break-on-Success?
The auto-test-and-fix phase loops up to 6 times:
- **Automatic recovery**: Fixes are verified immediately
- **Efficiency**: Breaks early when all tests pass
- **Safety**: Max iterations prevent infinite loops

## File Structure

```
.claude/
├── workflow.yml              # Main configuration (this file is generated)
├── WORKFLOW_DESIGN.md        # Design documentation (source of truth)
├── agent_prompts.md          # Detailed agent prompt templates
├── architecture.md           # System architecture
└── state/                    # Runtime state files
    ├── test_results.json     # Test execution results
    ├── failure_summary.json  # Failure classification
    ├── {module}_failures.json # Module-specific failures
    └── {module}_fixes.json   # Module-specific fixes
```

## Regenerating workflow.yml

To regenerate the workflow configuration:

1. **Review this design document** - Ensure all design decisions are current
2. **Update agent_prompts.md** - Modify agent prompts if needed
3. **Use Claude Code to generate** - Provide this document as context:
   ```
   Read .claude/WORKFLOW_DESIGN.md and .claude/agent_prompts.md
   Generate .claude/workflow.yml following the structure and design decisions
   ```
4. **Validate the configuration**:
   ```bash
   python3 -c "import yaml; yaml.safe_load(open('.claude/workflow.yml'))"
   ```
5. **Test with dry-run** (if available)

## Configuration Validation Checklist

When regenerating workflow.yml, verify:

- [ ] All phase dependencies are correct
- [ ] All agent names are consistent across phases
- [ ] All output paths use `.claude/state/` directory
- [ ] All condition expressions are supported by orchestrator
- [ ] File names in prompts match output field values
- [ ] Auto-commit messages are descriptive
- [ ] Loop configuration has max_iterations and break_on_success
- [ ] Module paths in prompts match actual directory structure

## Orchestrator Condition Patterns

The orchestrator supports these condition patterns:

1. `test_results.failed > 0` - Check if tests failed
2. `problem_analysis.problems.length > 0` - Check if problems exist
3. `{filename} exists and not empty` - Check if file exists with content

Example: `perception_failures.json exists and not empty`

## Common Issues and Solutions

### Issue: Agent reads wrong file
**Solution**: Ensure prompt references match output field values

### Issue: Condition not working
**Solution**: Use supported condition patterns (see above)

### Issue: Agents run when they shouldn't
**Solution**: Check condition logic and file content structure

### Issue: Loop doesn't break
**Solution**: Verify test_results.json has correct structure with "failed" field

## Version History

- 2024-05-13: Initial design documentation
- 2024-05-13: Added condition pattern support for file existence checks
- 2024-05-13: Fixed test_results.json file name inconsistencies

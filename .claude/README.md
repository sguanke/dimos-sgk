# Go2 Person Following - Multi-Agent Workflow

This directory contains configuration files for orchestrating multiple Claude Code agents to build the Go2 person following system.

## Quick Start

```bash
# Install orchestrator dependencies
pip install -r requirements.txt

# Run the multi-agent workflow
python orchestrator.py
```

## Workflow Overview

The workflow consists of 4 phases executed by 3 specialized agents:

### Phase 1: Planning
- **Agent**: Plan agent
- **Task**: Create detailed implementation plan
- **Output**: `.claude/plan.md`

### Phase 2: Implementation (Sequential)
- **Agent 1 (Coder)**: Implement source code
  - Runs in isolated worktree
  - Creates all source files, configs, and documentation
  - Output: `.claude/state/coder.json`

- **Agent 2 (Test-Writer)**: Write test suite
  - Runs in separate isolated worktree
  - Reads coder's implementation
  - Creates comprehensive tests
  - Output: `.claude/state/test-writer.json`

### Phase 3: Review
- **Agent**: Review agent
- **Task**: Review code and tests for quality and compliance
- **Output**: `.claude/state/review.md`

### Phase 4: Integration
- **Agent**: General-purpose agent
- **Task**: Merge worktrees, resolve conflicts, run tests
- **Output**: `.claude/state/integration.json`

## Configuration Files

### `.claude/workflow.yml`
Main workflow definition:
- Phase dependencies
- Agent assignments
- Isolation strategy (worktrees)
- Error handling rules

### `.claude/agent_prompts.md`
Detailed instructions for each agent:
- Coder agent: implementation requirements
- Test-writer agent: testing requirements
- Review agent: review checklist

### `CLAUDE.md`
Project documentation for all agents:
- Architecture decisions
- Technology stack
- Code standards
- Safety requirements
- Conflict resolution rules

## Agent Isolation

Each implementation agent runs in an isolated git worktree:
- **Coder worktree**: `.claude/worktrees/coder/`
- **Test-writer worktree**: `.claude/worktrees/test-writer/`

This prevents conflicts during parallel/sequential work and allows clean merging.

## State Management

Agent execution state is saved in `.claude/state/`:
- `planning_state.json` - Planning phase status
- `coder.json` - Coder agent output
- `test-writer.json` - Test-writer agent output
- `review.md` - Review report
- `integration.json` - Integration results
- `failed.json` - Failure information (if any)

## Error Handling

- **Max retries**: 2 attempts per phase
- **On failure**: Save state and exit
- **Recovery**: Re-run `orchestrator.py` to resume from last successful phase

## Customization

### Modify Agent Behavior
Edit `.claude/agent_prompts.md` to change agent instructions.

### Change Workflow
Edit `.claude/workflow.yml` to:
- Add/remove phases
- Change agent types
- Modify dependencies
- Enable parallel execution

### Update Architecture
Edit `CLAUDE.md` to change:
- Technology stack
- Code standards
- Safety requirements
- Component structure

## Monitoring Progress

Watch the orchestrator output for:
- Phase transitions
- Agent execution status
- Error messages
- Completion confirmation

Check `.claude/state/` for detailed agent outputs.

## Expected Runtime

- Planning: ~5 minutes
- Coder: ~20-30 minutes
- Test-writer: ~15-20 minutes
- Review: ~5-10 minutes
- Integration: ~5 minutes

**Total**: ~50-70 minutes for complete workflow

## Troubleshooting

### Agent fails with permission error
Check `.claude/settings.local.json` and add required permissions.

### Worktree conflicts
Manually inspect `.claude/worktrees/` and resolve conflicts, or delete worktrees and re-run.

### Review fails
Check `.claude/state/review.md` for specific issues and manually fix before re-running.

### Integration fails
Check test output in `.claude/state/integration.json` and fix failing tests.

## Manual Override

You can run individual phases manually:

```bash
# Run planning only
claude code --agent Plan --prompt "$(cat .claude/agent_prompts.md | grep -A 50 'Planning Agent')"

# Run coder in worktree
claude code --worktree coder --prompt "$(cat .claude/agent_prompts.md | grep -A 100 'Coder Agent')"

# Run review
claude code --prompt "Review the code in .claude/worktrees/coder and .claude/worktrees/test-writer"
```

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    Orchestrator                         │
│                  (orchestrator.py)                      │
└────────────┬────────────────────────────────────────────┘
             │
             ├─► Phase 1: Planning
             │   └─► Plan Agent → .claude/plan.md
             │
             ├─► Phase 2: Implementation
             │   ├─► Coder Agent (worktree)
             │   │   └─► src/, config/, requirements.txt
             │   │
             │   └─► Test-Writer Agent (worktree)
             │       └─► tests/unit/, tests/integration/
             │
             ├─► Phase 3: Review
             │   └─► Review Agent
             │       └─► .claude/state/review.md
             │
             └─► Phase 4: Integration
                 └─► Merge worktrees → main branch
                     └─► Run tests → Final report
```

## Key Features

✓ **No human interaction required** - All decisions pre-defined in CLAUDE.md
✓ **Reproducible** - Same config produces same results
✓ **Isolated execution** - Agents work in separate worktrees
✓ **Automatic conflict resolution** - Rules defined in CLAUDE.md
✓ **Quality gates** - Review phase ensures standards compliance
✓ **State persistence** - Can resume after failures
✓ **Comprehensive logging** - All agent outputs saved

## Next Steps

After successful workflow completion:
1. Review the generated code in `src/`
2. Check test coverage report
3. Read review report in `.claude/state/review.md`
4. Test in simulation mode: `python src/main.py --mode simulation`
5. Deploy to Go2 hardware

# Multi-Agent Architecture Diagram

## Agent Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                         Orchestrator                            │
│                      (orchestrator.py)                          │
└────────────┬────────────────────────────────────────────────────┘
             │
             ├─► Phase 1: Planning
             │   └─► Plan Agent → .claude/plan.md
             │
             ├─► Phase 2: Parallel Implementation
             │   ├─► Perception Agent (worktree)
             │   │   └─► src/vision/
             │   │       ├── person_detector.py
             │   │       ├── person_tracker.py
             │   │       └── target_selector.py
             │   │
             │   ├─► Navigation Agent (worktree)
             │   │   └─► src/control/
             │   │       ├── motion_controller.py
             │   │       ├── distance_keeper.py
             │   │       └── path_planner.py
             │   │
             │   ├─► Localization Agent (worktree)
             │   │   └─► src/localization/, src/mapping/
             │   │       ├── odometry.py
             │   │       ├── imu_fusion.py
             │   │       ├── pose_estimator.py
             │   │       └── local_map.py
             │   │
             │   └─► Safety Agent (worktree)
             │       └─► src/safety/
             │           ├── safety_monitor.py
             │           ├── watchdog.py
             │           └── health_checker.py
             │
             ├─► Phase 3: Integration
             │   └─► Integration Agent (worktree)
             │       └─► Merge all modules + create:
             │           ├── src/dimos_integration/
             │           ├── src/main.py
             │           └── requirements.txt
             │
             ├─► Phase 4: Parallel Testing
             │   ├─► Unit Test Agent (worktree)
             │   │   └─► tests/unit/
             │   │
             │   ├─► Integration Test Agent (worktree)
             │   │   └─► tests/integration/
             │   │
             │   └─► Simulation Test Agent (worktree)
             │       └─► tests/simulation/
             │
             ├─► Phase 5: Review
             │   └─► Review Agent
             │       └─► .claude/state/review.md
             │
             └─► Phase 6: Final Integration
                 └─► Merge all worktrees → main branch
                     └─► Run tests → Final report
```

## Module Dependencies

```
┌─────────────────┐
│   Perception    │ ──┐
│  (Vision Data)  │   │
└─────────────────┘   │
                      │
┌─────────────────┐   │    ┌─────────────────┐
│  Localization   │ ──┼───►│   Integration   │
│  (Pose Data)    │   │    │   (Dimos Bus)   │
└─────────────────┘   │    └────────┬────────┘
                      │             │
┌─────────────────┐   │             │
│   Navigation    │ ──┘             │
│ (Motion Cmds)   │                 │
└─────────────────┘                 │
                                    │
┌─────────────────┐                 │
│     Safety      │ ◄───────────────┘
│   (Veto Power)  │
└─────────────────┘
```

## Data Flow

```
Camera → Perception Agent → Person Position
                              │
                              ▼
IMU/Odometry → Localization Agent → Robot Pose
                              │
                              ▼
                        Integration Layer
                        (Dimos Message Bus)
                              │
                              ▼
                        Navigation Agent → Motion Commands
                              │
                              ▼
                        Safety Agent → Validated Commands
                              │
                              ▼
                          Go2 Robot
```

## Agent Isolation Strategy

Each agent works in an isolated git worktree:

```
.claude/worktrees/
├── perception-agent/        # Vision module
├── navigation-agent/        # Control module
├── localization-agent/      # Localization module
├── safety-agent/            # Safety module
├── integration-agent/       # Integration layer
├── unit-test-agent/         # Unit tests
├── integration-test-agent/  # Integration tests
└── simulation-test-agent/   # Simulation tests
```

Benefits:
- **Parallel execution**: Multiple agents work simultaneously
- **No conflicts**: Each agent has isolated workspace
- **Clean merging**: Integration agent handles merge conflicts
- **Rollback**: Can discard individual agent work if needed

## Communication Between Agents

Agents communicate through:
1. **Shared plan**: `.claude/plan.md` (read by all)
2. **CLAUDE.md**: Architecture and standards (read by all)
3. **State files**: `.claude/state/*.json` (agent outputs)
4. **Worktree code**: Later agents read earlier agents' code

No direct agent-to-agent communication during execution.

## Execution Timeline

```
Time →

Planning:           [Plan Agent]
                         │
Implementation:     ┌────┴────┬────────┬──────────┬────────┐
(Parallel)          │ Percep  │  Nav   │  Local   │ Safety │
                    └────┬────┴────┬───┴────┬─────┴────┬───┘
                         │         │        │          │
Integration:        └────┴─────────┴────────┴──────────┘
                              [Integration Agent]
                                     │
Testing:                    ┌────────┼────────┐
(Parallel)                  │        │        │
                        [Unit]  [Integ]  [Simul]
                            │        │        │
Review:                     └────────┼────────┘
                              [Review Agent]
                                     │
Final:                        [Final Integration]
```

## Advantages of Multi-Agent Architecture

1. **Modularity**: Each agent focuses on one domain
2. **Parallelization**: Independent modules built simultaneously
3. **Expertise**: Each agent becomes expert in its domain
4. **Fault Isolation**: One agent failure doesn't affect others
5. **Scalability**: Easy to add more specialized agents
6. **Code Quality**: Specialized focus leads to better code
7. **Testing**: Separate test agents ensure comprehensive coverage
8. **Review**: Independent review of all work

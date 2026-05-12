# Configuration Issues and Recommendations

## Critical Issues Found

### 1. **Dependency Resolution Problem** ⚠️

**Issue**: Agent-level dependencies reference phase names, but orchestrator checks phase-level dependencies.

**Location**: `.claude/workflow.yml`

**Problem**:
```yaml
# Agents have dependencies on phases
- name: "perception-agent"
  dependencies: ["planning"]  # ← References phase name

# But phases don't have dependencies set
- name: "implementation-parallel"
  dependencies: []  # ← Empty!
```

**Impact**: The orchestrator won't wait for planning phase to complete before starting implementation agents.

**Fix**: Add phase-level dependencies:
```yaml
- name: "implementation-parallel"
  dependencies: ["planning"]  # ← Add this
  
- name: "implementation-integration"
  dependencies: ["implementation-parallel"]  # ← Add this
  
- name: "testing"
  dependencies: ["implementation-integration"]  # ← Add this
```

---

### 2. **Orchestrator Doesn't Support Agent-Level Dependencies**

**Issue**: `orchestrator.py` only checks phase-level dependencies, not agent-level dependencies within a phase.

**Location**: `orchestrator.py` line ~120

**Current Code**:
```python
def check_dependencies(self, phase: Dict, completed_phases: set) -> bool:
    dependencies = phase.get("dependencies", [])
    return all(dep in completed_phases for dep in dependencies)
```

**Problem**: This only checks `phase["dependencies"]`, not `agent["dependencies"]` for agents within the phase.

**Impact**: Agents in parallel phases might start before their dependencies are met.

---

### 3. **Agent Prompts Reference Wrong File Paths**

**Issue**: `agent_prompts.md` references detailed instructions, but `workflow.yml` has simplified prompts.

**Example**:
- `workflow.yml` says: "Focus ONLY on vision-related components"
- `agent_prompts.md` has 200+ lines of detailed instructions

**Problem**: Agents will only see the short prompt from `workflow.yml`, not the detailed instructions from `agent_prompts.md`.

**Fix**: Workflow prompts should reference the detailed prompts:
```yaml
prompt: |
  Read detailed instructions in .claude/agent_prompts.md under "Perception Agent" section.
  Implement the perception module according to those instructions.
```

---

### 4. **Safety Agent File Location Conflict**

**Issue**: Inconsistent file paths for safety_monitor.py

**In workflow.yml**:
```yaml
- src/control/safety_monitor.py  # ← In control/
```

**In agent_prompts.md**:
```yaml
- src/safety/safety_monitor.py  # ← In safety/
```

**In CLAUDE.md**:
```yaml
src/safety/
  ├── safety_monitor.py  # ← In safety/
```

**Fix**: Decide on one location. Recommend `src/safety/` since it's a safety module.

---

### 5. **Missing Worktree Access for Integration Agent**

**Issue**: Integration agent needs to read code from other agents' worktrees, but no mechanism to access them.

**Problem**: Git worktrees are isolated. Integration agent in its own worktree can't see other worktrees' code.

**Fix Options**:
1. Don't use worktree isolation for integration agent
2. Add explicit worktree path parameters
3. Use git commands to read from other worktrees

---

### 6. **Review Agent Can't Access Worktrees**

**Issue**: Review agent needs to read all code but isn't in a worktree and has no access mechanism.

**Similar to issue #5**.

---

### 7. **Test Agents Can't Access Implementation Code**

**Issue**: Test agents run in isolated worktrees but need to read implementation code from other worktrees.

**Problem**: Each test agent is isolated and can't see implementation code.

**Fix**: Test agents should either:
1. Not use worktree isolation
2. Have explicit mechanism to access implementation worktrees

---

## Medium Issues

### 8. **No Validation of Agent Outputs**

**Issue**: Orchestrator doesn't validate that agents actually created the expected files.

**Example**: If perception-agent fails to create `person_detector.py`, no error is raised until integration.

**Fix**: Add output validation after each agent completes.

---

### 9. **Hardcoded Claude Code Command**

**Issue**: `orchestrator.py` assumes `claude code` command exists and works.

**Problem**: 
- Command might be `claude` not `claude code`
- Might need different invocation
- No error handling for missing command

**Fix**: Make command configurable and add error handling.

---

### 10. **No Mechanism to Pass Context Between Agents**

**Issue**: Agents can't communicate findings or decisions to each other except through code.

**Example**: If perception-agent discovers camera resolution is different, navigation-agent won't know.

**Fix**: Add shared context file that agents can read/write.

---

## Minor Issues

### 11. **Inconsistent Agent Naming**

**In workflow.yml**: `perception-agent`, `navigation-agent` (with hyphens)
**In agent_prompts.md**: `Perception Agent`, `Navigation Agent` (with spaces)

**Fix**: Use consistent naming everywhere.

---

### 12. **Missing pytest Configuration**

**Issue**: `agent_prompts.md` references `pytest.ini` but it's not in workflow outputs.

**Fix**: Add pytest.ini to unit-test-agent outputs.

---

### 13. **No Mechanism to Handle Review Failures**

**Issue**: If review agent fails the code, workflow continues to final-integration anyway.

**Fix**: Add conditional execution based on review result.

---

### 14. **Circular Reference Risk**

**Issue**: Integration agent is told to read from "all agent worktrees" but it's also in a worktree.

**Potential Problem**: Might try to read from itself.

---

## Recommendations

### Priority 1 (Must Fix)
1. ✅ Fix phase-level dependencies in workflow.yml
2. ✅ Fix safety_monitor.py path inconsistency
3. ✅ Solve worktree access problem for integration/review/test agents

### Priority 2 (Should Fix)
4. ✅ Link workflow prompts to detailed agent_prompts.md
5. ✅ Add output validation in orchestrator
6. ✅ Add mechanism for review failure handling

### Priority 3 (Nice to Have)
7. ✅ Add shared context mechanism
8. ✅ Make claude command configurable
9. ✅ Add pytest.ini to outputs

---

## Suggested Fixes

I can create updated versions of the configuration files with these issues fixed. Would you like me to:

1. Fix the critical issues (dependencies, paths, worktree access)?
2. Update orchestrator.py to handle these cases?
3. Create a validation script to check configuration consistency?

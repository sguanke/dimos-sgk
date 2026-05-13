# 重新生成 Workflow 配置的最佳实践

## 概述

本文档描述如何安全、可重复地重新生成 `.claude/workflow.yml` 配置文件。

## 核心原则

1. **文档驱动** - 配置从设计文档生成，而非手工编写
2. **版本控制** - 所有变更都有清晰的 git 历史
3. **自动验证** - 使用脚本验证配置正确性
4. **可追溯性** - 记录每次变更的原因和影响

## 文件结构

```
.claude/
├── WORKFLOW_DESIGN.md           # 设计文档（源头真相）
├── WORKFLOW_BEST_PRACTICES.md   # 本文档
├── workflow.yml                 # 生成的配置（可重新生成）
├── agent_prompts.md             # Agent 提示词模板
├── validate_workflow.py         # 配置验证脚本
└── architecture.md              # 系统架构文档
```

## 重新生成流程

### 步骤 1: 备份当前配置

```bash
# 创建备份
cp .claude/workflow.yml .claude/workflow.yml.backup

# 或者创建带时间戳的备份
cp .claude/workflow.yml .claude/workflow.yml.$(date +%Y%m%d_%H%M%S)
```

### 步骤 2: 审查设计文档

确保设计文档是最新的：

```bash
# 检查设计文档
cat .claude/WORKFLOW_DESIGN.md

# 如果需要更新设计，先编辑这个文件
# 记录所有设计决策和变更原因
```

### 步骤 3: 使用 Claude Code 生成配置

在 Claude Code 中执行：

```
我需要重新生成 workflow.yml 配置文件。

请执行以下步骤：
1. 读取 .claude/WORKFLOW_DESIGN.md（设计文档）
2. 读取 .claude/agent_prompts.md（提示词模板）
3. 读取 .claude/architecture.md（系统架构）
4. 根据这些文档生成新的 .claude/workflow.yml
5. 确保遵循所有设计决策和最佳实践
6. 使用 validate_workflow.py 验证生成的配置

重要提醒：
- 所有 output 路径使用 .claude/state/ 目录
- 文件名在 prompt 和 output 字段中必须一致
- 使用 orchestrator 支持的 condition 模式
- 保持 auto_commit 和 commit_message 配置
```

### 步骤 4: 验证配置

```bash
# 1. YAML 语法验证
python3 -c "import yaml; yaml.safe_load(open('.claude/workflow.yml'))"

# 2. 配置一致性验证
python3 .claude/validate_workflow.py

# 3. 手工检查关键部分
grep -E "(output:|condition:)" .claude/workflow.yml
```

### 步骤 5: 对比变更

```bash
# 查看变更
git diff .claude/workflow.yml

# 或者与备份对比
diff .claude/workflow.yml.backup .claude/workflow.yml
```

### 步骤 6: 测试配置

```bash
# 选项 A: 在测试分支上运行完整工作流
git checkout -b test-workflow-config
python3 orchestrator.py

# 选项 B: 只验证配置加载
python3 -c "
from orchestrator import AgentOrchestrator
orch = AgentOrchestrator('.claude/workflow.yml')
print(f'Loaded {len(orch.workflow[\"project\"][\"phases\"])} phases')
"
```

### 步骤 7: 提交变更

```bash
# 提交新配置
git add .claude/workflow.yml .claude/WORKFLOW_DESIGN.md
git commit -m "Regenerate workflow.yml from design document

Changes:
- [描述主要变更]
- [说明变更原因]

Validated with validate_workflow.py"

# 推送到远程
git push origin <branch-name>
```

## 常见场景

### 场景 1: 添加新的 Agent

1. 更新 `WORKFLOW_DESIGN.md`，添加新 agent 的说明
2. 更新 `agent_prompts.md`，添加新 agent 的提示词模板
3. 重新生成 `workflow.yml`
4. 验证新 agent 的配置正确
5. 提交变更

### 场景 2: 修改 Agent 提示词

1. 更新 `agent_prompts.md` 中的提示词
2. 重新生成 `workflow.yml`
3. 对比变更，确保只有提示词部分改变
4. 提交变更

### 场景 3: 调整阶段依赖关系

1. 更新 `WORKFLOW_DESIGN.md` 中的依赖关系说明
2. 重新生成 `workflow.yml`
3. 使用 `validate_workflow.py` 验证依赖关系
4. 测试工作流执行顺序
5. 提交变更

### 场景 4: 修复配置错误

1. 在 `WORKFLOW_DESIGN.md` 的 "Common Issues" 部分记录问题
2. 更新设计文档中的相关部分
3. 重新生成 `workflow.yml`
4. 验证问题已修复
5. 提交变更，在 commit message 中引用问题

## 配置验证清单

每次重新生成后，检查以下项目：

### 基础结构
- [ ] YAML 语法正确（无解析错误）
- [ ] 包含所有必需的 key（project, phases, state_dir）
- [ ] 阶段数量正确（当前应该是 7 个）

### 阶段配置
- [ ] 所有阶段有唯一的 name
- [ ] 阶段依赖关系正确
- [ ] Loop 配置正确（max_iterations, break_on_success）

### Agent 配置
- [ ] 所有 agent 有 name 和 prompt
- [ ] Agent dependencies 正确
- [ ] Condition 表达式使用支持的模式
- [ ] Output 路径统一在 .claude/state/ 目录

### 文件引用
- [ ] Prompt 中引用的文件名与 output 字段一致
- [ ] test-runner-agent 输出 test_results.json
- [ ] debugger-agent 读取 test_results.json
- [ ] 各模块 fixer 读取对应的 {module}_failures.json

### Auto-commit 配置
- [ ] 所有实现和修复 agent 有 auto_commit: true
- [ ] Commit message 描述清晰

## 故障排查

### 问题：生成的配置与预期不符

**解决方案**：
1. 检查 WORKFLOW_DESIGN.md 是否准确描述了预期配置
2. 向 Claude Code 提供更详细的指令
3. 手工调整生成的配置，然后更新设计文档

### 问题：验证脚本报错

**解决方案**：
1. 查看具体错误信息
2. 根据错误类型修复配置
3. 如果是验证脚本的误报，更新验证逻辑

### 问题：Orchestrator 无法加载配置

**解决方案**：
1. 检查 YAML 语法
2. 确保所有必需字段存在
3. 检查文件路径是否正确

### 问题：Agent 执行时出错

**解决方案**：
1. 检查 agent 的 prompt 是否引用了正确的文件
2. 确认 condition 表达式正确
3. 验证 dependencies 配置

## 版本控制策略

### 分支策略

- **main/master**: 稳定的配置版本
- **feat/***: 新功能的配置变更
- **fix/***: 配置错误修复

### Commit Message 格式

```
<type>: <subject>

<body>

<footer>
```

类型：
- `feat`: 添加新功能（新 agent、新阶段）
- `fix`: 修复配置错误
- `refactor`: 重构配置结构
- `docs`: 更新设计文档
- `test`: 添加或更新验证脚本

示例：
```
feat: Add verification agent to auto-test-and-fix phase

- Add verification-agent after module fixers
- Verify all fixes before next iteration
- Update WORKFLOW_DESIGN.md with new agent description

Validated with validate_workflow.py
```

## 自动化建议

### 创建生成脚本（可选）

```bash
#!/bin/bash
# regenerate_workflow.sh

set -e

echo "Backing up current workflow..."
cp .claude/workflow.yml .claude/workflow.yml.backup

echo "Generating new workflow..."
# 这里可以调用 Claude Code CLI 或其他生成工具

echo "Validating new workflow..."
python3 .claude/validate_workflow.py

echo "Showing changes..."
git diff .claude/workflow.yml

echo "Done! Review changes and commit if satisfied."
```

### 添加 Pre-commit Hook（可选）

```bash
# .git/hooks/pre-commit
#!/bin/bash

# 如果 workflow.yml 被修改，自动验证
if git diff --cached --name-only | grep -q "workflow.yml"; then
    echo "Validating workflow.yml..."
    python3 .claude/validate_workflow.py
    if [ $? -ne 0 ]; then
        echo "Workflow validation failed. Commit aborted."
        exit 1
    fi
fi
```

## 总结

重新生成配置的关键是：

1. **始终从设计文档开始** - WORKFLOW_DESIGN.md 是源头真相
2. **自动化验证** - 使用 validate_workflow.py 捕获错误
3. **版本控制** - 记录所有变更和原因
4. **测试验证** - 在测试环境中验证新配置
5. **文档同步** - 保持设计文档与实际配置一致

遵循这些实践，可以安全、可重复地管理复杂的 workflow 配置。

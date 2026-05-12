# 自主测试和修复系统使用指南

## 📖 概述

本系统实现了完全自动化的"测试-分析-修复-验证"循环，能够：
- ✅ 自动运行所有测试（单元测试、集成测试、仿真测试）
- ✅ 智能分析测试失败的根本原因
- ✅ 自动修复常见的代码问题
- ✅ 验证修复效果并检测回归
- ✅ 迭代执行直到所有测试通过

## 🚀 快速开始

### 1. 使用增强版工作流

```bash
# 使用带自动修复功能的工作流
python orchestrator.py --workflow .claude/workflow_with_autofix.yml
```

### 2. 只运行测试-修复循环

如果代码已经实现，只想运行测试和修复：

```bash
# 修改orchestrator.py支持指定phase
python orchestrator.py --workflow .claude/workflow_with_autofix.yml --phase auto-test-and-fix
```

## 🏗️ 系统架构

### 测试-修复循环流程

```
开始
  ↓
┌─────────────────────────────────────┐
│ 1. Test Runner Agent                │
│ - 运行pytest收集所有测试结果         │
│ - 生成详细的失败报告                 │
│ - 输出: test_results.json           │
└─────────────────────────────────────┘
  ↓
  所有测试通过？
  ├─ YES → 完成 ✅
  └─ NO  → 继续
      ↓
┌─────────────────────────────────────┐
│ 2. Debugger Agent                   │
│ - 分析每个失败测试                   │
│ - 识别错误类型和根本原因             │
│ - 生成修复策略                       │
│ - 输出: problem_analysis.json       │
└─────────────────────────────────────┘
  ↓
┌─────────────────────────────────────┐
│ 3. Fixer Agent                      │
│ - 根据分析结果修复代码               │
│ - 应用各种修复策略                   │
│ - 提交并推送修复                     │
│ - 输出: fixes_applied.json          │
└─────────────────────────────────────┘
  ↓
┌─────────────────────────────────────┐
│ 4. Verification Agent               │
│ - 重新运行失败的测试                 │
│ - 检测是否引入回归                   │
│ - 如有回归则回滚                     │
│ - 输出: verification_results.json   │
└─────────────────────────────────────┘
  ↓
  达到最大迭代次数？
  ├─ YES → 报告失败 ❌
  └─ NO  → 返回步骤1
```

## 📋 Agent详解

### 1. Test Runner Agent

**职责**: 运行所有测试并收集详细结果

**执行的命令**:
```bash
# 安装测试依赖
pip install pytest pytest-cov pytest-json-report pytest-html

# 运行测试
pytest tests/ \
  --verbose \
  --tb=long \
  --junit-xml=.claude/state/junit.xml \
  --cov=src \
  --cov-report=json:.claude/state/coverage.json \
  --json-report \
  --json-report-file=.claude/state/test_results.json \
  --html=.claude/state/test_report.html
```

**输出文件**:
- `.claude/state/test_results.json` - 结构化测试结果
- `.claude/state/test_failures.json` - 失败测试详情
- `.claude/state/coverage.json` - 代码覆盖率报告
- `.claude/state/test_report.html` - HTML测试报告

**输出格式示例**:
```json
{
  "total": 150,
  "passed": 142,
  "failed": 8,
  "skipped": 0,
  "duration": 45.2,
  "coverage": 85.3,
  "failures": [
    {
      "id": "failure_1",
      "test_file": "tests/unit/test_person_detector.py",
      "test_name": "test_detect_person_in_frame",
      "error_type": "AssertionError",
      "error_message": "Expected 1 detection, got 0",
      "traceback": "...",
      "source_file": "src/vision/person_detector.py",
      "source_line": 45
    }
  ]
}
```

### 2. Debugger Agent

**职责**: 分析测试失败原因并生成修复策略

**分析的错误类型**:
1. **AssertionError** - 断言失败，逻辑错误
2. **AttributeError** - 缺少属性或方法
3. **TypeError** - 类型不匹配
4. **ImportError** - 导入错误
5. **IndexError** - 数组越界
6. **KeyError** - 字典键不存在
7. **ValueError** - 值错误

**修复策略**:
- `add_initialization_check` - 添加初始化检查
- `fix_logic_error` - 修正逻辑错误
- `add_error_handling` - 添加错误处理
- `fix_type_conversion` - 修正类型转换
- `fix_import` - 修正导入语句
- `add_boundary_check` - 添加边界检查
- `fix_key_access` - 修正字典访问

**输出格式示例**:
```json
{
  "problems": [
    {
      "id": "problem_1",
      "failure_id": "failure_1",
      "test_file": "tests/unit/test_person_detector.py",
      "test_name": "test_detect_person_in_frame",
      "source_file": "src/vision/person_detector.py",
      "source_function": "detect_persons",
      "root_cause": "YOLO model not initialized before inference",
      "error_category": "initialization_error",
      "fix_strategy": "add_initialization_check",
      "affected_lines": [45, 46, 47],
      "suggested_fix": "Add: if self.model is None: self._load_model()",
      "confidence": 0.95
    }
  ]
}
```

### 3. Fixer Agent

**职责**: 根据分析结果自动修复代码

**修复示例**:

#### 初始化检查
```python
# 修复前
def detect_persons(self, frame):
    results = self.model(frame)  # model可能是None
    return results

# 修复后
def detect_persons(self, frame):
    if self.model is None:
        self._load_model()
    results = self.model(frame)
    return results
```

#### 类型转换
```python
# 修复前
def set_speed(self, speed):
    self.speed = speed  # speed可能是字符串

# 修复后
def set_speed(self, speed):
    self.speed = float(speed)
```

#### 边界检查
```python
# 修复前
def get_detection(self, index):
    return self.detections[index]  # 可能越界

# 修复后
def get_detection(self, index):
    if 0 <= index < len(self.detections):
        return self.detections[index]
    return None
```

#### 错误处理
```python
# 修复前
def load_config(self, path):
    with open(path) as f:
        return json.load(f)  # 文件可能不存在

# 修复后
def load_config(self, path):
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"Config file not found: {path}")
        return {}
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in config: {path}")
        return {}
```

**输出格式示例**:
```json
{
  "fixes": [
    {
      "problem_id": "problem_1",
      "file": "src/vision/person_detector.py",
      "lines_modified": [45, 46],
      "fix_type": "add_initialization_check",
      "description": "Added model initialization check before inference",
      "commit_sha": "abc123def456"
    }
  ]
}
```

### 4. Verification Agent

**职责**: 验证修复效果并检测回归

**验证步骤**:
1. 重新运行之前失败的测试
2. 运行完整测试套件检测回归
3. 比较修复前后的测试结果
4. 如果发现回归，自动回滚

**回归检测**:
```bash
# 如果检测到新的测试失败
git revert HEAD --no-edit
echo "Regression detected, reverted changes"
```

**输出格式示例**:
```json
{
  "fixed": ["failure_1", "failure_2"],
  "still_failing": ["failure_3"],
  "new_failures": [],
  "success_rate": 0.67,
  "regression_detected": false,
  "total_tests": 150,
  "passed": 148,
  "failed": 2
}
```

## 🔄 循环控制

### 配置参数

在 `workflow_with_autofix.yml` 中配置：

```yaml
- name: "auto-test-and-fix"
  loop:
    max_iterations: 6        # 最大迭代次数
    break_on_success: true   # 所有测试通过时提前退出
```

### 退出条件

循环会在以下情况退出：

1. ✅ **成功退出**: 所有测试通过（`test_results.failed == 0`）
2. ⏱️ **达到最大迭代次数**: 完成6次迭代后仍有失败
3. ❌ **Agent执行失败**: 任何agent执行失败

### 迭代日志示例

```
🔄 Loop iteration 1/6
────────────────────────────────────────
🤖 Running agent: test-runner-agent
  Total: 150, Passed: 142, Failed: 8
🤖 Running agent: debugger-agent
  Analyzed 8 failures, identified 8 problems
🤖 Running agent: fixer-agent
  Applied 8 fixes
🤖 Running agent: verification-agent
  Fixed: 6, Still failing: 2
  ⚠️  Still have 2 failing test(s)

🔄 Loop iteration 2/6
────────────────────────────────────────
🤖 Running agent: test-runner-agent
  Total: 150, Passed: 148, Failed: 2
🤖 Running agent: debugger-agent
  Analyzed 2 failures, identified 2 problems
🤖 Running agent: fixer-agent
  Applied 2 fixes
🤖 Running agent: verification-agent
  Fixed: 2, Still failing: 0
  ✅ All tests passed (0 failures)

✅ Success condition met after 2 iteration(s)
Breaking loop early
```

## 📊 状态文件

所有状态文件保存在 `.claude/state/` 目录：

| 文件 | 描述 |
|------|------|
| `test_results.json` | 测试运行结果 |
| `test_failures.json` | 失败测试详情 |
| `problem_analysis.json` | 问题分析报告 |
| `fixes_applied.json` | 应用的修复记录 |
| `verification_results.json` | 验证结果 |
| `coverage.json` | 代码覆盖率 |
| `junit.xml` | JUnit格式测试报告 |
| `test_report.html` | HTML测试报告 |

## 🎯 使用场景

### 场景1: 完整开发流程

从零开始开发项目，包含自动测试和修复：

```bash
python orchestrator.py --workflow .claude/workflow_with_autofix.yml
```

这会执行：
1. Planning - 创建实现计划
2. Implementation - 并行实现各模块
3. Integration - 集成所有模块
4. Testing - 编写测试用例
5. **Auto-Test-Fix** - 自动运行测试并修复问题（最多3次迭代）
6. Review - 代码审查
7. Final Integration - 最终集成

### 场景2: 只运行测试和修复

代码已经实现，只需要测试和修复：

```bash
# 需要修改orchestrator.py支持--phase参数
python orchestrator.py --workflow .claude/workflow_with_autofix.yml --phase auto-test-and-fix
```

### 场景3: 手动触发单个Agent

```bash
# 只运行测试
claude --prompt "$(cat .claude/workflow_with_autofix.yml | yq '.project.phases[] | select(.name == "auto-test-and-fix") | .agents[0].prompt')"

# 只运行问题分析
claude --prompt "$(cat .claude/workflow_with_autofix.yml | yq '.project.phases[] | select(.name == "auto-test-and-fix") | .agents[1].prompt')"
```

## 📈 成功指标

系统会跟踪以下指标：

- **自动修复率**: 能够自动修复的测试失败比例
- **平均迭代次数**: 平均需要多少次迭代才能通过所有测试
- **回归率**: 修复过程中引入新bug的比例
- **覆盖率提升**: 测试覆盖率的提升幅度

查看最终报告：

```bash
cat .claude/state/final-integration.json
```

## ⚠️ 限制和注意事项

### 能够自动修复的问题

✅ **可以修复**:
- 未初始化的变量
- 简单的类型转换错误
- 缺少的错误处理
- 边界检查缺失
- 简单的逻辑错误
- 导入路径错误

❌ **无法修复**:
- 复杂的算法设计错误
- 需要重构的架构问题
- 依赖外部服务或硬件的问题
- 需要领域知识的业务逻辑错误
- 性能优化问题

### 最佳实践

1. **设置合理的最大迭代次数**: 通常3次足够，避免无限循环
2. **人工审查自动修复**: 修复后仍需人工审查确保质量
3. **监控回归**: 关注 `verification_results.json` 中的回归检测
4. **保持测试质量**: 高质量的测试用例是自动修复的基础
5. **逐步增加复杂度**: 先修复简单问题，再处理复杂问题

## 🔍 调试和故障排除

### 查看详细日志

```bash
# 查看最新的orchestrator日志
ls -lt .claude/logs/orchestrator_*.log | head -1 | awk '{print $9}' | xargs cat

# 查看测试输出
cat .claude/state/test_report.html  # 在浏览器中打开

# 查看问题分析
cat .claude/state/problem_analysis.json | jq '.'

# 查看应用的修复
cat .claude/state/fixes_applied.json | jq '.'
```

### 常见问题

**Q: 循环一直无法通过所有测试怎么办？**

A: 检查 `.claude/state/verification_results.json` 中的 `still_failing` 列表，这些可能是需要人工修复的复杂问题。

**Q: 修复引入了回归怎么办？**

A: Verification Agent会自动检测并回滚。查看日志了解回滚原因。

**Q: 如何跳过某些测试？**

A: 在测试文件中使用 `@pytest.mark.skip` 或修改pytest配置。

**Q: 如何调整迭代次数？**

A: 修改 `workflow_with_autofix.yml` 中的 `max_iterations` 参数。

## 🚀 未来增强

计划中的功能：

1. **机器学习辅助**: 使用历史修复数据训练模型提高准确率
2. **并行修复**: 对独立的问题并行执行修复
3. **增量测试**: 只运行受影响的测试加快反馈
4. **修复建议排序**: 根据置信度和影响范围排序
5. **交互式修复**: 对不确定的修复请求人工确认
6. **性能优化**: 缓存测试结果，避免重复运行

## 📚 相关文档

- [自动修复系统设计文档](.claude/auto_fix_design.md) - 详细的技术设计
- [工作流配置](.claude/workflow_with_autofix.yml) - 完整的工作流定义
- [Agent提示词](.claude/agent_prompts.md) - 各个agent的详细指令
- [项目架构](CLAUDE.md) - 项目整体架构和规范

## 💡 示例输出

### 成功案例

```
🔄 Loop iteration 1/6
────────────────────────────────────────
🤖 Test Runner: 150 tests, 8 failed
🤖 Debugger: Analyzed 8 problems
🤖 Fixer: Applied 8 fixes
🤖 Verification: 6 fixed, 2 still failing

🔄 Loop iteration 2/6
────────────────────────────────────────
🤖 Test Runner: 150 tests, 2 failed
🤖 Debugger: Analyzed 2 problems
🤖 Fixer: Applied 2 fixes
🤖 Verification: 2 fixed, 0 still failing

✅ All tests passed!
✅ Success condition met after 2 iterations
📊 Auto-fix statistics:
  - Total problems: 10
  - Successfully fixed: 10
  - Fix rate: 100%
  - Iterations: 2
```

### 部分成功案例

```
🔄 Loop iteration 1/6
────────────────────────────────────────
🤖 Test Runner: 150 tests, 10 failed
🤖 Debugger: Analyzed 10 problems
🤖 Fixer: Applied 10 fixes
🤖 Verification: 7 fixed, 3 still failing

🔄 Loop iteration 2/6
────────────────────────────────────────
🤖 Test Runner: 150 tests, 3 failed
🤖 Debugger: Analyzed 3 problems
🤖 Fixer: Applied 3 fixes
🤖 Verification: 1 fixed, 2 still failing

🔄 Loop iteration 3/6
────────────────────────────────────────
🤖 Test Runner: 150 tests, 2 failed
🤖 Debugger: Analyzed 2 problems
🤖 Fixer: Applied 2 fixes
🤖 Verification: 0 fixed, 2 still failing

... (继续迭代)

🔄 Loop iteration 6/6
────────────────────────────────────────
🤖 Test Runner: 150 tests, 2 failed
🤖 Debugger: Analyzed 2 problems
🤖 Fixer: Applied 2 fixes
🤖 Verification: 0 fixed, 2 still failing

⚠️  Reached max iterations (6)
❌ 2 tests still failing
📊 Auto-fix statistics:
  - Total problems: 15
  - Successfully fixed: 13
  - Fix rate: 86.7%
  - Remaining issues require manual intervention
```

## 🎓 总结

自主测试和修复系统能够：
- ✅ 大幅减少手动调试时间
- ✅ 自动修复70-90%的常见问题
- ✅ 提供详细的问题分析报告
- ✅ 防止回归的引入
- ✅ 持续提高代码质量

但仍需要：
- ⚠️ 人工审查自动修复的代码
- ⚠️ 处理复杂的架构和算法问题
- ⚠️ 编写高质量的测试用例
- ⚠️ 定期维护和优化修复策略

# 自主测试和修复系统设计

## 🎯 目标

实现完全自动化的测试-修复循环：
1. 自动运行测试（单元测试、集成测试、仿真测试）
2. 智能分析测试失败原因
3. 自主定位问题代码
4. 自动修复bug
5. 验证修复效果
6. 迭代直到所有测试通过或达到最大尝试次数

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    测试-修复循环                              │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
        ┌──────────────────────────────────────┐
        │  Phase 1: Test Execution             │
        │  - test-runner-agent                 │
        │  - 运行pytest收集所有测试结果         │
        │  - 生成详细的失败报告                 │
        └──────────────────────────────────────┘
                            │
                            ▼
                    ┌──────────────┐
                    │ 所有测试通过？ │
                    └──────────────┘
                       │          │
                    YES│          │NO
                       │          │
                       ▼          ▼
              ┌─────────┐   ┌──────────────────────────────┐
              │ 完成退出 │   │ Phase 2: Problem Analysis    │
              └─────────┘   │ - debugger-agent             │
                            │ - 分析堆栈跟踪和错误信息      │
                            │ - 定位问题代码位置            │
                            │ - 识别失败根因                │
                            └──────────────────────────────┘
                                        │
                                        ▼
                            ┌──────────────────────────────┐
                            │ Phase 3: Code Fixing         │
                            │ - fixer-agent                │
                            │ - 根据分析结果修复代码        │
                            │ - 提交修复并推送              │
                            └──────────────────────────────┘
                                        │
                                        ▼
                            ┌──────────────────────────────┐
                            │ Phase 4: Verification        │
                            │ - 重新运行失败的测试          │
                            │ - 验证修复是否有效            │
                            └──────────────────────────────┘
                                        │
                                        ▼
                                ┌──────────────┐
                                │ 达到最大次数？ │
                                └──────────────┘
                                   │          │
                                YES│          │NO
                                   │          │
                                   ▼          │
                            ┌─────────┐      │
                            │报告失败  │      │
                            │退出循环  │      │
                            └─────────┘      │
                                             │
                                             └──► 返回Phase 1
```

## 📋 新增Agent定义

### 1. Test Runner Agent

**职责**: 运行所有测试并收集结果

**输入**:
- 已实现的代码（src/）
- 测试代码（tests/）
- pytest配置

**输出**:
- `.claude/state/test_results.json` - 结构化测试结果
- `.claude/state/test_failures.json` - 失败测试详情
- `.claude/logs/pytest_output.log` - 完整pytest输出

**执行逻辑**:
```python
# 1. 安装依赖
pip install -r requirements.txt

# 2. 运行pytest收集详细信息
pytest tests/ \
  --verbose \
  --tb=long \
  --junit-xml=.claude/state/junit.xml \
  --cov=src \
  --cov-report=json:.claude/state/coverage.json \
  --json-report \
  --json-report-file=.claude/state/test_results.json

# 3. 解析结果
- 总测试数
- 通过/失败/跳过数量
- 失败测试的详细信息（文件、行号、错误信息、堆栈跟踪）
- 代码覆盖率

# 4. 生成失败报告
{
  "total": 150,
  "passed": 142,
  "failed": 8,
  "failures": [
    {
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

**职责**: 分析测试失败原因并定位问题

**输入**:
- `.claude/state/test_failures.json` - 失败测试详情
- 源代码文件
- 测试代码文件

**输出**:
- `.claude/state/problem_analysis.json` - 问题分析报告

**分析策略**:
```python
for failure in test_failures:
    # 1. 读取失败测试代码
    test_code = read_file(failure.test_file)
    
    # 2. 读取被测试的源代码
    source_code = read_file(failure.source_file)
    
    # 3. 分析错误类型
    if failure.error_type == "AssertionError":
        # 断言失败 - 逻辑错误
        analyze_assertion_failure()
    elif failure.error_type == "AttributeError":
        # 属性错误 - 接口不匹配
        analyze_interface_mismatch()
    elif failure.error_type == "ImportError":
        # 导入错误 - 依赖问题
        analyze_dependency_issue()
    elif failure.error_type == "TypeError":
        # 类型错误 - 参数类型不匹配
        analyze_type_mismatch()
    
    # 4. 定位根因
    root_cause = identify_root_cause(
        test_code, 
        source_code, 
        failure.traceback
    )
    
    # 5. 生成修复建议
    fix_suggestion = generate_fix_suggestion(root_cause)
```

**输出格式**:
```json
{
  "problems": [
    {
      "id": "problem_1",
      "test_file": "tests/unit/test_person_detector.py",
      "test_name": "test_detect_person_in_frame",
      "source_file": "src/vision/person_detector.py",
      "source_function": "detect_persons",
      "root_cause": "YOLO model not initialized before inference",
      "error_category": "initialization_error",
      "fix_strategy": "Add model initialization check in detect_persons()",
      "affected_lines": [45, 46, 47],
      "suggested_fix": "Add: if self.model is None: self._load_model()"
    }
  ]
}
```

### 3. Fixer Agent

**职责**: 根据分析结果自动修复代码

**输入**:
- `.claude/state/problem_analysis.json` - 问题分析
- 源代码文件

**输出**:
- 修复后的代码文件
- `.claude/state/fixes_applied.json` - 修复记录

**修复策略**:
```python
for problem in problems:
    # 1. 读取问题代码
    source_code = read_file(problem.source_file)
    
    # 2. 根据修复策略应用修复
    if problem.fix_strategy == "add_initialization_check":
        fixed_code = add_initialization_check(
            source_code,
            problem.source_function,
            problem.affected_lines
        )
    elif problem.fix_strategy == "fix_type_mismatch":
        fixed_code = fix_type_conversion(
            source_code,
            problem.affected_lines
        )
    elif problem.fix_strategy == "add_error_handling":
        fixed_code = add_try_except(
            source_code,
            problem.affected_lines
        )
    
    # 3. 写回文件
    write_file(problem.source_file, fixed_code)
    
    # 4. 记录修复
    log_fix(problem.id, problem.source_file, "applied")

# 5. 提交修复
git add .
git commit -m "Auto-fix: {problem descriptions}"
git push
```

### 4. Verification Agent

**职责**: 验证修复效果

**输入**:
- 修复后的代码
- 之前失败的测试列表

**输出**:
- `.claude/state/verification_results.json` - 验证结果

**验证逻辑**:
```python
# 1. 只运行之前失败的测试
failed_tests = load_failed_tests()
test_args = " ".join([f"{t.test_file}::{t.test_name}" for t in failed_tests])

# 2. 运行测试
pytest {test_args} --verbose --tb=short

# 3. 分析结果
results = {
    "fixed": [],      # 修复成功的测试
    "still_failing": [], # 仍然失败的测试
    "new_failures": []   # 新引入的失败
}

# 4. 如果有新失败，回滚修复
if len(results["new_failures"]) > 0:
    git revert HEAD
    report_regression()
```

## 🔄 循环控制逻辑

在 `orchestrator.py` 中实现循环控制：

```python
class TestFixLoop:
    def __init__(self, max_iterations=3):
        self.max_iterations = max_iterations
        self.iteration = 0
        
    def run(self):
        while self.iteration < self.max_iterations:
            self.iteration += 1
            logger.info(f"🔄 Test-Fix Iteration {self.iteration}/{self.max_iterations}")
            
            # Phase 1: Run tests
            test_results = self.run_test_runner_agent()
            
            # Check if all tests passed
            if test_results["failed"] == 0:
                logger.info("✅ All tests passed!")
                return True
            
            logger.warning(f"❌ {test_results['failed']} tests failed")
            
            # Phase 2: Analyze problems
            analysis = self.run_debugger_agent(test_results)
            
            # Phase 3: Fix code
            fixes = self.run_fixer_agent(analysis)
            
            # Phase 4: Verify fixes
            verification = self.run_verification_agent(fixes)
            
            # Check if fixes worked
            if verification["still_failing"] == 0:
                logger.info("✅ All fixes successful!")
                # Run full test suite one more time
                continue
            else:
                logger.warning(f"⚠️  {len(verification['still_failing'])} tests still failing")
        
        # Max iterations reached
        logger.error(f"❌ Failed to fix all tests after {self.max_iterations} iterations")
        return False
```

## 📝 修改后的 workflow.yml

在现有workflow基础上添加新的phase：

```yaml
# ... 现有的phases ...

- name: "auto-test-and-fix"
  dependencies: ["testing"]
  loop:
    max_iterations: 3
    break_on_success: true
  agents:
    - name: "test-runner-agent"
      agent: "general-purpose"
      prompt: |
        Run all tests and collect detailed results.
        
        Steps:
        1. Install dependencies: pip install -r requirements.txt
        2. Run pytest with detailed output:
           pytest tests/ --verbose --tb=long \
             --junit-xml=.claude/state/junit.xml \
             --cov=src --cov-report=json:.claude/state/coverage.json \
             --json-report --json-report-file=.claude/state/test_results.json
        3. Parse results and create failure report
        4. Save to .claude/state/test_failures.json
        
        Output format:
        {
          "total": N,
          "passed": N,
          "failed": N,
          "failures": [detailed failure info]
        }
      output: ".claude/state/test_results.json"
      
    - name: "debugger-agent"
      agent: "general-purpose"
      condition: "test_results.failed > 0"
      prompt: |
        Analyze test failures and identify root causes.
        
        Read:
        - .claude/state/test_failures.json
        - Source code files mentioned in failures
        - Test code files
        
        For each failure:
        1. Identify error type (assertion, attribute, import, type)
        2. Read relevant source code
        3. Analyze root cause
        4. Generate fix strategy
        
        Output detailed analysis to .claude/state/problem_analysis.json
      dependencies: ["test-runner-agent"]
      output: ".claude/state/problem_analysis.json"
      
    - name: "fixer-agent"
      agent: "general-purpose"
      condition: "problem_analysis.problems.length > 0"
      prompt: |
        Fix code based on problem analysis.
        
        Read .claude/state/problem_analysis.json
        
        For each problem:
        1. Read source file
        2. Apply fix according to fix_strategy
        3. Write fixed code back
        4. Log the fix
        
        After all fixes:
        1. git add .
        2. git commit -m "Auto-fix: [list of fixes]"
        3. git push
        
        Output fixes applied to .claude/state/fixes_applied.json
      dependencies: ["debugger-agent"]
      output: ".claude/state/fixes_applied.json"
      auto_commit: true
      commit_message: "Auto-fix: Apply automated bug fixes based on test failures"
      
    - name: "verification-agent"
      agent: "general-purpose"
      prompt: |
        Verify that fixes resolved the test failures.
        
        Read .claude/state/test_failures.json to get list of failed tests
        
        Run only the previously failed tests:
        pytest [failed_test_list] --verbose --tb=short
        
        Analyze results:
        - Which tests are now passing (fixed)
        - Which tests are still failing (not fixed)
        - Any new test failures (regression)
        
        If new failures detected:
        - git revert HEAD
        - Report regression
        
        Output verification results to .claude/state/verification_results.json
      dependencies: ["fixer-agent"]
      output: ".claude/state/verification_results.json"
```

## 🛠️ Orchestrator 增强

修改 `orchestrator.py` 支持循环和条件执行：

```python
class EnhancedOrchestrator:
    def execute_phase_with_loop(self, phase_config):
        """执行带循环的phase"""
        loop_config = phase_config.get("loop", {})
        max_iterations = loop_config.get("max_iterations", 1)
        break_on_success = loop_config.get("break_on_success", False)
        
        for iteration in range(max_iterations):
            logger.info(f"🔄 Loop iteration {iteration + 1}/{max_iterations}")
            
            # 执行phase中的所有agents
            results = self.execute_agents(phase_config["agents"])
            
            # 检查是否应该提前退出
            if break_on_success and self.check_success_condition(results):
                logger.info("✅ Success condition met, breaking loop")
                break
                
        return results
    
    def check_agent_condition(self, agent_config, context):
        """检查agent的执行条件"""
        condition = agent_config.get("condition")
        if not condition:
            return True
            
        # 解析条件表达式
        # 例如: "test_results.failed > 0"
        return eval_condition(condition, context)
    
    def execute_agent_with_condition(self, agent_config, context):
        """条件执行agent"""
        if not self.check_agent_condition(agent_config, context):
            logger.info(f"⏭️  Skipping {agent_config['name']} (condition not met)")
            return None
            
        return self.execute_agent(agent_config)
```

## 📊 状态文件格式

### test_results.json
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "total": 150,
  "passed": 142,
  "failed": 8,
  "skipped": 0,
  "duration": 45.2,
  "coverage": 85.3
}
```

### test_failures.json
```json
{
  "failures": [
    {
      "id": "failure_1",
      "test_file": "tests/unit/test_person_detector.py",
      "test_name": "test_detect_person_in_frame",
      "test_line": 25,
      "error_type": "AssertionError",
      "error_message": "Expected 1 detection, got 0",
      "traceback": "...",
      "source_file": "src/vision/person_detector.py",
      "source_line": 45
    }
  ]
}
```

### problem_analysis.json
```json
{
  "problems": [
    {
      "id": "problem_1",
      "failure_id": "failure_1",
      "root_cause": "Model not initialized",
      "fix_strategy": "add_initialization_check",
      "confidence": 0.95,
      "suggested_fix": "Add model initialization check"
    }
  ]
}
```

### fixes_applied.json
```json
{
  "fixes": [
    {
      "problem_id": "problem_1",
      "file": "src/vision/person_detector.py",
      "lines_modified": [45, 46],
      "fix_type": "add_initialization_check",
      "commit_sha": "abc123"
    }
  ]
}
```

### verification_results.json
```json
{
  "fixed": ["failure_1", "failure_2"],
  "still_failing": ["failure_3"],
  "new_failures": [],
  "success_rate": 0.75
}
```

## 🎯 使用示例

```bash
# 运行完整的测试-修复循环
python orchestrator.py --phase auto-test-and-fix

# 查看测试结果
cat .claude/state/test_results.json

# 查看问题分析
cat .claude/state/problem_analysis.json

# 查看应用的修复
cat .claude/state/fixes_applied.json

# 查看验证结果
cat .claude/state/verification_results.json
```

## 🔍 智能修复策略

### 常见问题类型和修复策略

1. **初始化错误**
   - 检测: `AttributeError: 'NoneType' object has no attribute`
   - 修复: 添加初始化检查或延迟初始化

2. **类型不匹配**
   - 检测: `TypeError: expected int, got str`
   - 修复: 添加类型转换或类型检查

3. **导入错误**
   - 检测: `ImportError: cannot import name`
   - 修复: 修正导入路径或添加缺失的依赖

4. **断言失败**
   - 检测: `AssertionError: expected X, got Y`
   - 修复: 分析逻辑错误，修正算法实现

5. **索引错误**
   - 检测: `IndexError: list index out of range`
   - 修复: 添加边界检查或修正索引逻辑

6. **键错误**
   - 检测: `KeyError: 'key_name'`
   - 修复: 添加键存在性检查或使用get()方法

## 📈 成功指标

- **自动修复率**: 能够自动修复的测试失败比例
- **迭代次数**: 平均需要多少次迭代才能通过所有测试
- **回归率**: 修复过程中引入新bug的比例
- **覆盖率提升**: 测试覆盖率的提升幅度

## ⚠️ 限制和注意事项

1. **复杂逻辑错误**: 涉及算法设计的错误可能无法自动修复
2. **架构问题**: 需要重构的问题超出自动修复范围
3. **外部依赖**: 依赖外部服务或硬件的问题难以自动修复
4. **最大迭代次数**: 设置合理的上限避免无限循环
5. **人工审查**: 自动修复后仍需人工审查确保质量

## 🚀 未来增强

1. **机器学习辅助**: 使用历史修复数据训练模型提高修复准确率
2. **并行修复**: 对独立的问题并行执行修复
3. **增量测试**: 只运行受影响的测试加快反馈速度
4. **修复建议排序**: 根据置信度和影响范围排序修复建议
5. **交互式修复**: 对不确定的修复请求人工确认

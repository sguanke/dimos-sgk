# dimos-sgk

基于多智能体开发工作流构建的Go2机器狗人员跟随系统。

## 项目概述

本项目为宇树Go2机器狗实现了一个人员跟随系统，使用dimos框架构建。系统通过计算机视觉检测和跟踪指定人员，然后控制机器人在保持安全距离的同时进行跟随。

## 多智能体开发工作流

本项目采用创新的多智能体开发方法，由多个专门的AI智能体协作构建完整系统：

### 实现智能体
- **感知智能体 (Perception Agent)** - 视觉检测和跟踪 (YOLO + DeepSORT)
- **导航智能体 (Navigation Agent)** - 运动控制和路径规划
- **定位智能体 (Localization Agent)** - 机器人位姿估计和建图
- **安全智能体 (Safety Agent)** - 安全监控和紧急处理
- **集成智能体 (Integration Agent)** - 系统集成与dimos框架对接

### 测试智能体
- **单元测试智能体 (Unit Test Agent)** - 全面的单元测试
- **集成测试智能体 (Integration Test Agent)** - 模块交互测试
- **仿真测试智能体 (Simulation Test Agent)** - 端到端场景测试

### 🆕 自动测试和修复智能体
- **测试运行智能体 (Test Runner Agent)** - 自动运行所有测试并收集结果
- **调试智能体 (Debugger Agent)** - 智能分析测试失败原因
- **修复智能体 (Fixer Agent)** - 自动修复常见代码问题
- **验证智能体 (Verification Agent)** - 验证修复效果并检测回归

> 💡 **自动测试-修复循环**: 系统能够自动运行测试、分析失败原因、修复代码并验证，最多迭代3次直到所有测试通过！

## 快速开始

### 前置要求

- Python 3.10+
- 已配置远程仓库访问权限的Git
- PyYAML（用于编排器）

### 安装

```bash
# 克隆仓库
git clone <repository-url>
cd dimos-sgk

# 安装编排器依赖
pip install -r requirements.txt
```

### 运行多智能体工作流

#### 标准工作流（不含自动修复）
```bash
# 启动自动化开发工作流
python orchestrator.py
```

#### 🆕 增强工作流（含自动测试和修复）
```bash
# 使用带自动测试-修复循环的工作流
python orchestrator.py --workflow .claude/workflow_with_autofix.yml
```

编排器将会：
1. 按正确顺序执行所有智能体
2. 每个模块完成后自动提交并推送代码
3. **🆕 自动运行测试并修复失败的测试（最多3次迭代）**
4. 将详细进度记录到控制台和 `.claude/logs/`
5. 为每个模块创建独立分支

### 🔄 自动测试-修复循环

增强工作流包含智能的测试-修复循环：

```
运行测试 → 分析失败 → 自动修复 → 验证修复 → 重复（最多6次）
```

**能够自动修复的问题**:
- ✅ 未初始化的变量
- ✅ 类型转换错误
- ✅ 缺少的错误处理
- ✅ 边界检查缺失
- ✅ 简单的逻辑错误
- ✅ 导入路径错误

**自动修复率**: 通常能修复70-90%的常见问题

详细文档: [自动测试和修复系统使用指南](.claude/AUTO_FIX_GUIDE.md)

### 监控进度

```bash
# 实时查看日志
tail -f .claude/logs/orchestrator_*.log

# 检查智能体输出
ls -la .claude/state/

# 🆕 查看测试结果
cat .claude/state/test_results.json

# 🆕 查看问题分析
cat .claude/state/problem_analysis.json

# 🆕 查看应用的修复
cat .claude/state/fixes_applied.json

# 🆕 查看HTML测试报告（在浏览器中打开）
open .claude/state/test_report.html

# 查看创建的分支
git branch -r
```

## 项目结构

```
dimos-sgk/
├── src/                          # 源代码（由智能体生成）
│   ├── vision/                   # 感知模块
│   ├── control/                  # 导航模块
│   ├── localization/             # 定位模块
│   ├── mapping/                  # 建图模块
│   ├── safety/                   # 安全模块
│   ├── dimos_integration/        # Dimos集成
│   └── main.py                   # 入口点
├── tests/                        # 测试套件（由智能体生成）
│   ├── unit/                     # 单元测试
│   ├── integration/              # 集成测试
│   └── simulation/               # 仿真测试
├── config/                       # 配置文件
├── .claude/                      # 多智能体工作流配置
│   ├── workflow.yml              # 智能体工作流定义
│   ├── agent_prompts.md          # 智能体详细指令
│   ├── architecture.md           # 架构文档
│   ├── config_issues.md          # 配置问题记录
│   ├── fixes_applied.md          # 已应用的修复
│   ├── state/                    # 智能体执行状态
│   ├── logs/                     # 执行日志
│   └── worktrees/                # 智能体隔离工作空间
├── CLAUDE.md                     # 项目架构和标准
├── orchestrator.py               # 多智能体编排器
├── requirements.txt              # Python依赖
└── README.md                     # 本文件
```

## 配置文件说明

### 核心配置文件

#### `CLAUDE.md`
**作用**: 项目架构和开发规范的主文档
**用途**:
- 定义项目技术栈和架构决策
- 规定代码质量标准和安全要求
- 说明模块结构和职责划分
- 提供开发命令和测试方法
- 定义冲突解决规则
**使用者**: 所有智能体都会读取此文件作为开发指南

#### `orchestrator.py`
**作用**: 多智能体工作流的执行引擎
**用途**:
- 解析workflow.yml并按顺序执行各阶段
- 管理智能体依赖关系和执行顺序
- 自动提交和推送代码到远程分支
- 记录详细日志到控制台和文件
- 处理错误和重试机制
**使用者**: 用户通过命令行运行此脚本启动工作流

#### `requirements.txt`
**作用**: Python依赖包列表
**用途**:
- 列出编排器所需的Python包（当前仅pyyaml）
- 后续会由integration-agent添加项目运行时依赖
**使用者**: 用户在安装阶段使用

### .claude/ 目录配置文件

#### `.claude/workflow.yml`
**作用**: 智能体工作流的核心定义文件（标准版）
**用途**:
- 定义6个执行阶段（planning, implementation, integration, testing, review, final-integration）
- 配置8个智能体的名称、提示词、依赖关系
- 设置自动提交和推送的分支名称
- 配置错误处理策略（重试次数等）
- 指定输出文件路径和状态目录
**使用者**: orchestrator.py读取此文件执行工作流

#### 🆕 `.claude/workflow_with_autofix.yml`
**作用**: 增强版工作流定义文件（含自动测试-修复循环）
**用途**:
- 包含标准工作流的所有功能
- 新增 `auto-test-and-fix` 阶段，包含4个智能体：
  - Test Runner Agent - 运行测试并收集结果
  - Debugger Agent - 分析失败原因
  - Fixer Agent - 自动修复代码
  - Verification Agent - 验证修复效果
- 配置循环参数（最大迭代次数、成功退出条件）
- 支持条件执行（只在有失败时运行修复）
**使用者**: 通过 `python orchestrator.py --workflow .claude/workflow_with_autofix.yml` 使用

#### `.claude/agent_prompts.md`
**作用**: 每个智能体的详细实现指令
**用途**:
- 为每个智能体提供200+行的详细实现指南
- 定义输入输出、代码质量要求、安全规范
- 提供配置文件模板和代码示例
- 说明测试策略和覆盖率要求
- 列出禁止事项和注意事项
**使用者**: 各智能体通过workflow.yml中的提示词引用此文件

#### `.claude/architecture.md`
**作用**: 系统架构可视化文档
**用途**:
- 提供智能体工作流程图
- 展示模块依赖关系图
- 说明数据流向
- 解释智能体隔离策略
- 描述多智能体架构的优势
**使用者**: 开发者理解系统架构，智能体参考设计

#### 🆕 `.claude/auto_fix_design.md`
**作用**: 自动测试和修复系统的详细技术设计
**用途**:
- 说明测试-修复循环的架构
- 定义4个自动修复智能体的职责和接口
- 提供状态文件格式规范
- 说明智能修复策略和错误分类
- 列出系统限制和未来增强方向
**使用者**: 开发者理解自动修复机制，扩展修复策略

#### 🆕 `.claude/AUTO_FIX_GUIDE.md`
**作用**: 自动测试和修复系统的用户使用指南
**用途**:
- 提供快速开始指南和使用示例
- 详细说明每个智能体的功能和输出
- 展示修复前后的代码对比
- 提供故障排除和调试方法
- 列出成功指标和最佳实践
**使用者**: 用户学习如何使用自动测试-修复功能

#### `.claude/config_issues.md`
**作用**: 配置问题诊断报告
**用途**:
- 记录发现的14个配置问题
- 分类为关键、中等、次要问题
- 提供问题描述、影响和修复建议
- 作为配置审查的检查清单
**使用者**: 开发者排查配置问题时参考

#### `.claude/fixes_applied.md`
**作用**: 已应用修复的详细记录
**用途**:
- 记录7个关键问题的修复方案
- 说明修复前后的配置对比
- 提供修复的影响分析
- 列出剩余注意事项和建议
**使用者**: 开发者了解配置演进历史

#### `.claude/state/`
**作用**: 智能体执行状态存储目录
**用途**:
- 保存每个智能体的输出JSON文件
- 存储review.md代码审查报告
- 记录final-integration.json最终总结
- 保存失败状态用于恢复
- 🆕 保存测试结果和修复记录：
  - `test_results.json` - 测试运行结果
  - `test_failures.json` - 失败测试详情
  - `problem_analysis.json` - 问题分析报告
  - `fixes_applied.json` - 应用的修复记录
  - `verification_results.json` - 修复验证结果
  - `coverage.json` - 代码覆盖率报告
  - `test_report.html` - HTML测试报告
**使用者**: orchestrator.py写入，用户和后续智能体读取

#### `.claude/logs/`
**作用**: 执行日志存储目录
**用途**:
- 保存带时间戳的详细执行日志
- 记录每个智能体的启动、执行、完成过程
- 记录Git提交和推送操作
- 记录错误信息和警告
- 提供性能指标（执行时间等）
**使用者**: 用户监控进度和排查问题

#### `.claude/worktrees/`
**作用**: Git worktree隔离工作空间
**用途**:
- 为实现智能体提供隔离的代码空间
- 避免并行开发时的代码冲突
- 允许集成智能体读取各模块代码
- 支持独立的分支开发
**使用者**: Git自动管理，智能体读写

### 其他配置文件

#### `.claude/settings.local.json`
**作用**: Claude Code本地权限配置
**用途**:
- 配置自动允许的Git命令
- 避免频繁的权限确认提示
**使用者**: Claude Code运行时读取

## 工作流阶段

### 阶段1: 规划 (Planning)
- 创建详细的实现计划
- 定义模块接口和依赖关系

### 阶段2: 并行实现 (Parallel Implementation)
四个智能体同时工作在不同模块上：
- **感知智能体** → `perception-module` 分支
- **导航智能体** → `navigation-module` 分支
- **定位智能体** → `localization-module` 分支
- **安全智能体** → `safety-module` 分支

每个智能体完成后自动提交并推送代码。

### 阶段3: 集成 (Integration)
- **集成智能体** 合并所有模块
- 创建dimos通信层
- 推送到 `integration-module` 分支

### 阶段4: 并行测试 (Parallel Testing)
三个智能体同时编写测试：
- **单元测试智能体** → `unit-tests` 分支
- **集成测试智能体** → `integration-tests` 分支
- **仿真测试智能体** → `simulation-tests` 分支

### 🆕 阶段5: 自动测试和修复 (Auto Test-Fix Loop)
**仅在使用 `workflow_with_autofix.yml` 时执行**

四个智能体循环执行（最多6次迭代）：
1. **测试运行智能体** - 运行所有测试，收集失败信息
2. **调试智能体** - 分析失败原因，生成修复策略
3. **修复智能体** - 自动修复代码并提交
4. **验证智能体** - 验证修复效果，检测回归

**退出条件**:
- ✅ 所有测试通过（提前退出）
- ⏱️ 达到最大迭代次数（6次）
- ❌ 任何智能体执行失败

**示例输出**:
```
🔄 Loop iteration 1/6
  Test Runner: 150 tests, 8 failed
  Debugger: Analyzed 8 problems
  Fixer: Applied 8 fixes
  Verification: 6 fixed, 2 still failing

🔄 Loop iteration 2/6
  Test Runner: 150 tests, 2 failed
  Debugger: Analyzed 2 problems
  Fixer: Applied 2 fixes
  Verification: 2 fixed, 0 still failing

✅ All tests passed!
✅ Success after 2 iterations
```

### 阶段6: 审查 (Review)
- 审查所有代码和测试
- 检查标准合规性
- 验证安全要求
- 🆕 检查测试覆盖率和修复质量

### 阶段7: 最终集成 (Final Integration)
- 合并所有测试代码
- 运行完整测试套件
- 创建最终总结报告
- 🆕 包含自动修复统计信息

## 生成的分支

工作流完成后，将生成以下分支：

```
origin/perception-module      # 视觉检测和跟踪
origin/navigation-module      # 运动控制和路径规划
origin/localization-module    # 位姿估计和建图
origin/safety-module          # 安全监控
origin/integration-module     # 系统集成
origin/unit-tests            # 单元测试套件
origin/integration-tests     # 集成测试套件
origin/simulation-tests      # 仿真测试套件
```

## 日志和状态

### 执行日志
位置: `.claude/logs/orchestrator_YYYYMMDD_HHMMSS.log`

包含内容：
- 智能体执行时间线
- Git提交和推送操作
- 错误消息和警告
- 性能指标

### 智能体状态
位置: `.claude/state/`

文件列表：
- `perception-agent.json` - 感知智能体输出
- `navigation-agent.json` - 导航智能体输出
- `localization-agent.json` - 定位智能体输出
- `safety-agent.json` - 安全智能体输出
- `integration-agent.json` - 集成智能体输出
- `unit-test-agent.json` - 单元测试智能体输出
- `integration-test-agent.json` - 集成测试智能体输出
- `simulation-test-agent.json` - 仿真测试智能体输出
- `review.md` - 代码审查报告
- `final-integration.json` - 最终总结

## 配置修改

### 修改工作流配置
编辑 `.claude/workflow.yml` 可以：
- 修改智能体提示词
- 更改分支名称
- 调整提交消息
- 配置错误处理

### 修改智能体指令
编辑 `.claude/agent_prompts.md` 可以：
- 更新实现要求
- 更改代码标准
- 修改测试策略

### 修改项目标准
编辑 `CLAUDE.md` 可以：
- 定义架构决策
- 设置代码质量标准
- 指定安全要求

## 开发命令

工作流完成后，可以使用以下命令：

```bash
# 设置环境
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 运行测试
pytest tests/

# 运行特定测试套件
pytest tests/unit/
pytest tests/integration/
pytest tests/simulation/

# 运行测试并生成覆盖率报告
pytest --cov=src --cov-report=html tests/

# 🆕 运行测试并生成详细报告（用于自动修复）
pytest tests/ \
  --verbose \
  --tb=long \
  --junit-xml=.claude/state/junit.xml \
  --cov=src \
  --cov-report=json:.claude/state/coverage.json \
  --json-report \
  --json-report-file=.claude/state/test_results.json \
  --html=.claude/state/test_report.html

# 🆕 只运行之前失败的测试
pytest tests/unit/test_detector.py::test_detect_person --verbose

# 运行系统（仿真模式）
python src/main.py --mode simulation

# 在硬件上运行
python src/main.py --mode hardware --robot-ip 192.168.123.161

# 调试模式（带可视化）
python src/main.py --mode simulation --debug --visualize
```

## 技术栈

- **框架**: dimos（分布式智能多智能体操作系统）
- **硬件**: 宇树Go2机器狗
- **语言**: Python 3.10+
- **视觉**: OpenCV + YOLOv8 人员检测
- **跟踪**: DeepSORT 多目标跟踪
- **控制**: PID控制器 + 动态窗口法(DWA)
- **通信**: ROS2 Humble 进程间通信

## 安全特性

- 100ms内紧急停止
- 碰撞避免，最小0.3m间隙
- 看门狗定时器监控
- 系统健康检查
- 最大速度限制：0.8 m/s
- 所有运动命令由安全监控器验证

## 故障排除

### 工作流在某个阶段失败
查看 `.claude/logs/` 获取详细错误信息，查看 `.claude/state/` 获取智能体输出。

### Git推送失败
确保你有：
- 已配置远程仓库
- 推送权限
- 网络连接

### 智能体超时
在 `orchestrator.py` 中增加超时时间（默认：每个智能体1小时）。

### Worktree访问问题
检查 `.claude/worktrees/` 目录是否存在，智能体是否有读取权限。

### 🆕 自动修复循环无法通过所有测试
1. 查看 `.claude/state/verification_results.json` 中的 `still_failing` 列表
2. 这些可能是需要人工修复的复杂问题
3. 查看 `.claude/state/problem_analysis.json` 了解分析结果
4. 手动修复后重新运行工作流

### 🆕 修复引入了回归
- Verification Agent会自动检测并回滚
- 查看日志了解回滚原因
- 检查 `.claude/state/verification_results.json` 中的 `new_failures`

### 🆕 测试报告查看
```bash
# 在浏览器中打开HTML报告
open .claude/state/test_report.html  # macOS
xdg-open .claude/state/test_report.html  # Linux
start .claude/state/test_report.html  # Windows

# 查看JSON格式的详细结果
cat .claude/state/test_results.json | jq '.'
```

## 配置文件依赖关系

```
orchestrator.py
    ↓ 读取
workflow.yml
    ↓ 引用
agent_prompts.md
    ↓ 参考
CLAUDE.md
    ↓ 定义
architecture.md
```

所有智能体都会读取：
- `CLAUDE.md` - 架构和标准
- `agent_prompts.md` - 详细指令
- `.claude/plan.md` - 实现计划（由planning阶段生成）

## 贡献

本项目使用自动化多智能体开发。要修改：

1. 更新 `.claude/` 中的配置文件
2. 运行 `python orchestrator.py`
3. 审查生成的代码和测试
4. 根据需要合并分支

## 许可证

[您的许可证]

## 联系方式

[您的联系信息]

## 致谢

- 使用Claude Code多智能体工作流构建
- 基于dimos框架
- 为宇树Go2机器人平台设计

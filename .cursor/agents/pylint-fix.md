---
name: pylint-fix
model: inherit
description: 识别并修复pylint错误
---

---
name: pylint-fix
model: inherit
description: 识别并修复pylint错误
---

修复 Pylint 检查报告的问题，确保代码质量符合项目规范和软件工程最佳实践。

## 核心原则

1. **简单问题直接修复** — 明确的代码风格、命名、格式问题快速处理
2. **复杂问题深度分析** — 难修复的问题需识别是否是架构设计不合理导致
3. **修复质量保证** — 不破坏功能、不简单注释、不防御编程、找到根本原因

## 执行流程

### 1. 运行 Pylint 检查

```bash
cd backend
make lint-pylint
# 或指定文件：uv run pylint <file_path>
```

### 2. 问题分类与修复策略

#### 2.1 简单问题（直接修复）

**特征**：规则明确、修复方式唯一、不影响逻辑

| 问题类型 | 代码 | 修复方式 |
|---------|------|---------|
| 命名不规范 | C0103 | 按 snake_case（变量/函数）或 PascalCase（类）重命名 |
| 缺少文档字符串 | C0114/C0115/C0116 | 添加有意义的 Google 风格文档字符串 |
| 行过长 | C0301 | 合理换行或提取变量 |
| 导入顺序错误 | C0411 | 按标准库→第三方→本地顺序排列 |
| 未使用的导入 | W0611 | 删除或添加到 `TYPE_CHECKING` 块 |
| 未使用的变量 | W0612 | 删除或使用 `_` 前缀表示有意忽略 |
| 重复代码 | R0801 | 提取公共函数或基类 |

#### 2.2 中等问题（需分析后修复）

**特征**：可能有多种修复方式，需要理解上下文

| 问题类型 | 代码 | 分析要点 |
|---------|------|---------|
| 函数过长 | R0915 | 识别可提取的子函数，保持单一职责 |
| 参数过多 | R0913 | 考虑使用配置对象、dataclass 或 Builder 模式 |
| 分支过多 | R0912 | 使用策略模式、字典映射或提前返回 |
| 类属性过多 | R0902 | 考虑拆分类或使用组合 |
| 返回语句过多 | R0911 | 重构为单一出口或使用 Result 类型 |
| 圈复杂度过高 | R1260 | 分解复杂逻辑，提取辅助方法 |

#### 2.3 架构问题（需深度分析）

**特征**：反映设计层面的问题，简单修复可能掩盖真实问题

| 问题类型 | 代码 | 可能的根本原因 |
|---------|------|---------------|
| 循环导入 | R0401 | 模块职责不清、分层不合理 |
| 过度耦合 | R0904 | 类承担了过多职责，需要拆分 |
| 重复代码 | R0801 | 缺少抽象层或公共基类 |
| 访问保护成员 | W0212 | 接口设计不完善，需要暴露公共方法 |
| 全局语句 | W0603 | 状态管理不当，考虑依赖注入 |

**处理流程**：
1. 分析问题根源，识别设计缺陷
2. 评估重构范围和影响
3. 如需较大重构，记录为技术债务并提出改进建议
4. 小范围修复时遵循渐进式改进原则

### 3. 修复优先级

1. **P0 - 立即修复**：错误级别（E）、致命级别（F）
2. **P1 - 高优先级**：警告级别（W）中的逻辑问题
3. **P2 - 中优先级**：重构建议（R）
4. **P3 - 低优先级**：代码规范（C）、信息（I）

## 禁止行为 ❌

### 1. 禁止简单注释抑制

```python
# ❌ 错误：简单添加 pylint: disable 注释
def func():  # pylint: disable=too-many-branches
    ...

# ✅ 正确：重构代码解决问题
def func():
    return self._handle_by_type.get(type_, self._handle_default)(data)
```

**例外情况**：仅当以下条件全部满足时允许使用 disable 注释：
- 问题是误报或与项目特殊需求冲突
- 在注释中说明原因
- 使用最小范围的禁用（行级 > 函数级 > 模块级）

```python
# ✅ 合理的例外：明确说明原因
# pylint: disable=no-member  # SQLAlchemy 动态属性，Pylint 无法识别
session.query(User).filter_by(id=user_id)
```

### 2. 禁止防御性编程掩盖问题

```python
# ❌ 错误：添加无意义的检查来消除警告
def process(data):
    if data is not None:  # 添加此检查只为消除 possibly-none 警告
        return data.value
    return None  # data 在此上下文永远不为 None

# ✅ 正确：修复上游类型标注或使用断言表达意图
def process(data: Data) -> str:  # 正确标注非 None 类型
    return data.value

# 或者在确实需要断言时：
def process(data: Data | None) -> str:
    assert data is not None, "data should be set by caller"
    return data.value
```

### 3. 禁止破坏功能的修复

```python
# ❌ 错误：删除"未使用"的代码但实际上有副作用
# 原代码
_registry = {}  # 看似未使用，实际被装饰器填充

# ✅ 正确：理解代码意图后决定
_registry: dict[str, Handler] = {}  # 添加类型注解，保留功能
```

### 4. 禁止过度重构

- 不要为了消除一个警告而大规模重构
- 不要引入不必要的抽象层
- 不要创建"未来可能用到"的通用方案

## 最佳实践 ✅

### 1. 理解再修复

```bash
# 先理解问题上下文
uv run pylint <file> --msg-template='{path}:{line}: [{msg_id}({symbol})] {msg}'
```

修复前问自己：
- 这段代码的作用是什么？
- 为什么会产生这个警告？
- 修复后会影响什么？

### 2. 渐进式修复

对于复杂问题，采用小步重构：

```python
# Step 1: 提取方法
def _validate_input(self, data):
    ...

# Step 2: 提取类（如果方法增多）
class InputValidator:
    ...

# Step 3: 使用依赖注入（如果需要解耦）
def __init__(self, validator: InputValidator):
    ...
```

### 3. 保持一致性

遵循项目现有的代码风格和模式：
- 使用 `core/types.py` 中定义的类型
- 遵循分层架构（API → Services → Models）
- 复用 `utils/` 中的工具函数

### 4. 文档字符串规范

```python
def process_message(
    self,
    message: str,
    options: ProcessOptions | None = None,
) -> Result[Response, ProcessError]:
    """处理用户消息并返回响应。

    Args:
        message: 用户输入的消息文本
        options: 可选的处理配置

    Returns:
        成功时返回 Response 对象，失败时返回 ProcessError

    Raises:
        ValidationError: 当消息格式无效时抛出
    """
```

## 验证完成标准

修复完成后必须满足：

1. ✅ `make lint-pylint` 通过（或仅剩可接受的例外）
2. ✅ 相关测试通过（`make test`）
3. ✅ 代码功能未被破坏
4. ✅ 类型检查通过（`make lint-pyright`）
5. ✅ 无新增的代码质量问题

## 输出要求

修复完成后提供：

1. **问题统计**：修复的问题数量和类型分布
2. **关键修复说明**：架构级问题的分析和处理方式
3. **遗留问题**：无法在本次修复的问题及原因
4. **改进建议**：发现的技术债务或优化机会

## 相关资源

- Pylint 配置：`backend/pyproject.toml` ([tool.pylint] 部分)
- 代码规则检查：`.cursor/agents/code-rule-check.md`
- 类型定义：`backend/core/types.py`
- 项目架构：`AI-Agent系统架构设计文档.md`

---

**执行命令示例**：

```bash
# 1. 进入后端目录
cd backend

# 2. 运行 Pylint 检查
make lint-pylint

# 3. 查看特定文件的详细问题
uv run pylint services/agent.py --output-format=colorized

# 4. 修复后重新检查
make lint-pylint

# 5. 运行测试确保功能正常
make test
```

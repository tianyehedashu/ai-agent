# 权限系统测试文档

## 概述

本文档描述了为权限系统添加的测试用例，确保权限过滤、权限检查和权限上下文功能正常工作。

## 测试结构

```
tests/
├── unit/                          # 单元测试
│   ├── libs/
│   │   └── db/
│   │       ├── test_permission_context.py    # 权限上下文测试
│   │       └── test_base_repository.py       # Repository 基类测试
│   └── identity/
│       └── presentation/
│           └── test_permission_checks.py    # 权限检查函数测试
└── integration/                   # 集成测试
    └── libs/
        └── db/
            └── test_repository_permissions.py # Repository 权限过滤集成测试
```

## 测试覆盖

### 1. 权限上下文测试 (`test_permission_context.py`)

**测试内容**：
- ✅ 创建注册用户权限上下文
- ✅ 创建匿名用户权限上下文
- ✅ 创建管理员权限上下文
- ✅ 空权限上下文
- ✅ 权限上下文不可变性
- ✅ 设置和获取权限上下文
- ✅ 获取未设置的权限上下文
- ✅ 清除权限上下文
- ✅ 设置 None 上下文

**关键测试点**：
- `PermissionContext` 的属性（`is_admin`、`is_anonymous`、`has_identity`）
- ContextVar 的线程安全设置和获取
- 上下文清理机制

### 2. Repository 基类测试 (`test_base_repository.py`)

**测试内容**：
- ✅ `model_class` 属性
- ✅ `anonymous_user_id_column` 属性
- ✅ `user_id_column` 默认值
- ✅ 管理员绕过权限过滤
- ✅ 注册用户权限过滤
- ✅ 匿名用户权限过滤
- ✅ 无权限上下文时返回空结果
- ✅ `find_owned` 方法（管理员）
- ✅ `get_owned` 方法（权限检查）
- ✅ `count_owned` 方法

**关键测试点**：
- `_apply_ownership_filter` 方法的过滤逻辑
- 管理员绕过机制
- 不同用户类型的过滤行为

### 3. 权限检查函数测试 (`test_permission_checks.py`)

**测试内容**：

#### `check_ownership` 测试
- ✅ 所有者可以访问资源
- ✅ 非所有者不能访问资源
- ✅ 管理员可以访问所有资源
- ✅ 自定义资源名称

#### `check_ownership_or_public` 测试
- ✅ 所有者可以访问私有资源
- ✅ 任何人都可以访问公开资源
- ✅ 非所有者不能访问私有资源
- ✅ 管理员可以访问所有资源（包括私有）

#### `check_session_ownership` 测试
- ✅ 注册用户拥有自己的会话
- ✅ 注册用户不能访问其他用户的会话
- ✅ 匿名用户拥有自己的会话
- ✅ 匿名用户不能访问其他匿名用户的会话
- ✅ 管理员可以访问所有会话
- ✅ 管理员可以访问匿名用户的会话

**关键测试点**：
- 管理员绕过机制
- 注册用户和匿名用户的权限隔离
- 错误消息格式

### 4. Repository 权限过滤集成测试 (`test_repository_permissions.py`)

**测试内容**：

#### 会话仓储权限过滤
- ✅ `find_by_user` 根据权限上下文过滤
- ✅ `get_by_id` 根据权限上下文过滤
- ✅ 管理员可以访问所有会话
- ✅ 匿名用户根据 `anonymous_user_id` 过滤

#### Agent 仓储权限过滤
- ✅ `find_by_user` 根据权限上下文过滤
- ✅ 管理员可以访问所有 Agent

**关键测试点**：
- 实际数据库操作中的权限过滤
- 多用户数据隔离
- 管理员权限绕过
- 匿名用户权限隔离

## 运行测试

### 运行所有权限系统测试

```bash
# 运行所有权限系统测试
pytest tests/unit/libs/db/ tests/unit/identity/presentation/test_permission_checks.py tests/integration/libs/db/test_repository_permissions.py -v
```

### 运行特定测试文件

```bash
# 权限上下文测试
pytest tests/unit/libs/db/test_permission_context.py -v

# Repository 基类测试
pytest tests/unit/libs/db/test_base_repository.py -v

# 权限检查函数测试
pytest tests/unit/identity/presentation/test_permission_checks.py -v

# Repository 权限过滤集成测试
pytest tests/integration/libs/db/test_repository_permissions.py -v
```

### 运行特定测试类

```bash
# 运行 TestPermissionContext 测试
pytest tests/unit/libs/db/test_permission_context.py::TestPermissionContext -v

# 运行 TestCheckOwnership 测试
pytest tests/unit/identity/presentation/test_permission_checks.py::TestCheckOwnership -v
```

### 运行特定测试方法

```bash
# 运行单个测试
pytest tests/unit/libs/db/test_permission_context.py::TestPermissionContext::test_create_admin_context -v
```

## 测试覆盖率

### 已覆盖的功能

1. **权限上下文**
   - ✅ 创建和属性访问
   - ✅ ContextVar 操作
   - ✅ 上下文清理

2. **Repository 基类**
   - ✅ 权限过滤逻辑
   - ✅ 管理员绕过
   - ✅ 不同用户类型过滤

3. **权限检查函数**
   - ✅ `check_ownership`
   - ✅ `check_ownership_or_public`
   - ✅ `check_session_ownership`
   - ✅ 管理员绕过机制

4. **Repository 实现**
   - ✅ 会话仓储权限过滤
   - ✅ Agent 仓储权限过滤
   - ✅ 实际数据库操作

### 建议补充的测试

1. **中间件测试**
   - `PermissionContextMiddleware` 的请求处理
   - 权限上下文的自动设置

2. **依赖注入测试**
   - `get_current_user` 自动设置权限上下文
   - `require_role` 依赖工厂

3. **边界情况测试**
   - 并发请求的权限上下文隔离
   - 异常情况下的上下文清理

## 测试最佳实践

1. **使用 fixtures**
   - 使用 `test_user` fixture 创建测试用户
   - 使用 `db_session` fixture 获取数据库会话

2. **清理权限上下文**
   - 在测试中使用 `try/finally` 确保清理权限上下文
   - 避免测试之间的相互影响

3. **测试隔离**
   - 每个测试应该独立运行
   - 使用事务回滚确保数据隔离

4. **断言清晰**
   - 使用明确的断言消息
   - 验证权限检查的预期行为

## 相关文档

- [权限系统架构文档](../../docs/PERMISSION_SYSTEM_ARCHITECTURE.md)
- [代码规范](../../docs/CODE_STANDARDS.md)

"""Shared module - Cross-domain shared components.

目录结构:
- infrastructure/: 共享基础设施
  - auth/: 认证系统 (JWT, 密码加密)
  - config/: 配置服务
  - llm/: LLM 网关
  - observability/: 可观测性 (日志, 指标, 追踪)
  - orm/: ORM 基类
  - utils/: 工具函数
  - a2a/: Agent-to-Agent 通信
- kernel/: 核心类型定义
- presentation/: 共享表示层组件
- types.py: 共享类型定义
- interfaces.py: 共享接口协议
"""

# 配置文件说明

> **完整文档**：请参阅 [docs/CONFIGURATION.md](../docs/CONFIGURATION.md)

## 文件结构

```
config/
├── app.toml              # 基础配置（默认值）
├── app.development.toml  # 开发环境覆盖
├── app.staging.toml      # 预发环境覆盖
├── app.production.toml   # 生产环境覆盖
└── README.md             # 本文件
```

## 配置优先级

```
环境变量 > .env > app.{env}.toml > app.toml > 代码默认值
```

## 多环境配置

通过 `APP_ENV` 环境变量切换环境：

```bash
# 开发环境（默认）
export APP_ENV=development

# 预发环境
export APP_ENV=staging

# 生产环境
export APP_ENV=production
```

## 快速开始

### 1. 设置环境变量

```bash
# 复制示例配置
cp config/env.example .env

# 编辑 .env，填写 API Keys
```

### 2. 修改配置（可选）

编辑 `app.toml` 或对应环境的配置文件：

```toml
[simplemem]
enabled = true
extraction_model = "gpt-4o-mini"
```

### 3. 环境变量覆盖

```bash
# 任何配置都可以通过环境变量覆盖
export SIMPLEMEM_ENABLED=false
```

## 配置分类

| 类型 | 存放位置 | 示例 |
|------|---------|------|
| 敏感信息 | `.env` | API Keys、数据库密码 |
| 环境相关 | `.env` | DATABASE_URL、APP_ENV |
| 功能开关 | `app.toml` | simplemem.enabled |
| 模型配置 | `app.toml` | models.available |
| 环境特定 | `app.{env}.toml` | logging.level |

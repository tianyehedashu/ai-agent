"""
API Error Messages - API 错误消息常量

统一管理 API 错误消息，避免重复字面量
"""

# 资源未找到
AGENT_NOT_FOUND = "Agent not found"
SESSION_NOT_FOUND = "Session not found"
WORKFLOW_NOT_FOUND = "Workflow not found"
USER_NOT_FOUND = "User not found"
VERSION_NOT_FOUND = "Version not found"

# 权限错误
ACCESS_DENIED = "Access denied"
UNAUTHORIZED = "Unauthorized"
INSUFFICIENT_PERMISSIONS = "Insufficient permissions"

# 验证错误
INVALID_CREDENTIALS = "Invalid credentials"
INVALID_TOKEN = "Invalid token"
TOKEN_EXPIRED = "Token expired"

# 通用错误
INTERNAL_ERROR = "Internal server error"
BAD_REQUEST = "Bad request"

"""
Memory API - 记忆管理接口
"""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, ConfigDict, Field

from domains.agent.application.memory_service import MemoryService
from domains.identity.presentation.deps import AuthUser, check_ownership
from libs.api.deps import get_memory_service

router = APIRouter()


# =============================================================================
# Request/Response Schemas
# =============================================================================


class MemoryItem(BaseModel):
    """记忆条目"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    type: str
    content: str
    importance: float
    created_at: datetime
    metadata: dict[str, Any]


class MemorySearch(BaseModel):
    """记忆搜索请求"""

    model_config = ConfigDict(strict=True)

    query: str = Field(..., min_length=1, description="搜索查询")
    top_k: int = Field(default=10, ge=1, le=50, description="返回数量")
    type_filter: str | None = Field(default=None, description="类型过滤")


class MemoryCreate(BaseModel):
    """创建记忆请求"""

    model_config = ConfigDict(strict=True)

    type: str = Field(..., pattern="^(fact|episode|procedure|preference)$", description="记忆类型")
    content: str = Field(..., min_length=1, description="记忆内容")
    importance: float = Field(default=0.5, ge=0, le=1, description="重要性")
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据")


class ImportKnowledge(BaseModel):
    """导入知识请求"""

    model_config = ConfigDict(strict=True)

    content: str = Field(..., min_length=1, description="知识内容")
    source: str = Field(default="manual", description="来源")
    chunk_size: int = Field(default=1000, ge=100, le=5000, description="分块大小")


class ImportResponse(BaseModel):
    """导入响应"""

    status: str
    task_id: str
    message: str


# =============================================================================
# API Endpoints
# =============================================================================


@router.get("/", response_model=list[MemoryItem])
async def list_memories(
    current_user: AuthUser,
    memory_service: MemoryService = Depends(get_memory_service),
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    type_filter: str | None = None,
) -> list[MemoryItem]:
    """获取记忆列表"""
    memories = await memory_service.list_by_user(
        user_id=current_user.id,
        skip=skip,
        limit=limit,
        type_filter=type_filter,
    )
    return [MemoryItem.model_validate(m) for m in memories]


@router.post("/search", response_model=list[MemoryItem])
async def search_memories(
    request: MemorySearch,
    current_user: AuthUser,
    memory_service: MemoryService = Depends(get_memory_service),
) -> list[MemoryItem]:
    """搜索记忆"""
    memories = await memory_service.search(
        user_id=current_user.id,
        query=request.query,
        top_k=request.top_k,
        type_filter=request.type_filter,
    )
    return [MemoryItem.model_validate(m) for m in memories]


@router.post("/", response_model=MemoryItem, status_code=status.HTTP_201_CREATED)
async def create_memory(
    data: MemoryCreate,
    current_user: AuthUser,
    memory_service: MemoryService = Depends(get_memory_service),
) -> MemoryItem:
    """手动创建记忆"""
    memory = await memory_service.create(
        user_id=current_user.id,
        type=data.type,
        content=data.content,
        importance=data.importance,
        metadata=data.metadata,
    )
    return MemoryItem.model_validate(memory)


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    memory_id: str,
    current_user: AuthUser,
    memory_service: MemoryService = Depends(get_memory_service),
) -> None:
    """删除记忆"""
    memory = await memory_service.get_by_id_or_raise(memory_id)
    check_ownership(str(memory.user_id), current_user, "Memory")
    await memory_service.delete(memory_id)


@router.post("/import", response_model=ImportResponse, status_code=status.HTTP_202_ACCEPTED)
async def import_knowledge(
    data: ImportKnowledge,
    current_user: AuthUser,
    memory_service: MemoryService = Depends(get_memory_service),
) -> ImportResponse:
    """导入知识到记忆库"""
    task_id = await memory_service.import_knowledge(
        user_id=current_user.id,
        content=data.content,
        source=data.source,
        chunk_size=data.chunk_size,
    )
    return ImportResponse(
        status="processing",
        task_id=task_id,
        message="Knowledge import started",
    )

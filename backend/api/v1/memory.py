"""
Memory API - 记忆管理接口
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from api.deps import get_current_user
from models.user import User

router = APIRouter()


class MemoryItem(BaseModel):
    """记忆条目"""

    id: str
    type: str
    content: str
    importance: float
    access_count: int
    created_at: datetime
    last_accessed: datetime
    metadata: dict

    class Config:
        from_attributes = True


class MemorySearch(BaseModel):
    """记忆搜索请求"""

    query: str = Field(..., min_length=1, description="搜索查询")
    top_k: int = Field(default=10, ge=1, le=50, description="返回数量")
    type_filter: str | None = Field(default=None, description="类型过滤")


class MemoryCreate(BaseModel):
    """创建记忆请求"""

    type: str = Field(..., pattern="^(fact|episode|procedure)$", description="记忆类型")
    content: str = Field(..., min_length=1, description="记忆内容")
    importance: float = Field(default=0.5, ge=0, le=1, description="重要性")
    metadata: dict = Field(default_factory=dict, description="元数据")


@router.get("/", response_model=list[MemoryItem])
async def list_memories(
    current_user: User = Depends(get_current_user),
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    type_filter: str | None = None,
) -> list[MemoryItem]:
    """获取记忆列表"""
    from services.memory import MemoryService

    memory_service = MemoryService()
    memories = await memory_service.list_by_user(
        user_id=str(current_user.id),
        skip=skip,
        limit=limit,
        type_filter=type_filter,
    )
    return [MemoryItem.model_validate(m) for m in memories]


@router.post("/search", response_model=list[MemoryItem])
async def search_memories(
    request: MemorySearch,
    current_user: User = Depends(get_current_user),
) -> list[MemoryItem]:
    """搜索记忆"""
    from services.memory import MemoryService

    memory_service = MemoryService()
    memories = await memory_service.search(
        user_id=str(current_user.id),
        query=request.query,
        top_k=request.top_k,
        type_filter=request.type_filter,
    )
    return [MemoryItem.model_validate(m) for m in memories]


@router.post("/", response_model=MemoryItem, status_code=status.HTTP_201_CREATED)
async def create_memory(
    data: MemoryCreate,
    current_user: User = Depends(get_current_user),
) -> MemoryItem:
    """手动创建记忆"""
    from services.memory import MemoryService

    memory_service = MemoryService()
    memory = await memory_service.create(
        user_id=str(current_user.id),
        **data.model_dump(),
    )
    return MemoryItem.model_validate(memory)


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    memory_id: str,
    current_user: User = Depends(get_current_user),
) -> None:
    """删除记忆"""
    from services.memory import MemoryService

    memory_service = MemoryService()
    memory = await memory_service.get_by_id(memory_id)

    if not memory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory not found",
        )

    if str(memory.user_id) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    await memory_service.delete(memory_id)


class ImportKnowledge(BaseModel):
    """导入知识请求"""

    content: str = Field(..., min_length=1, description="知识内容")
    source: str = Field(default="manual", description="来源")
    chunk_size: int = Field(default=1000, ge=100, le=5000, description="分块大小")


@router.post("/import", status_code=status.HTTP_202_ACCEPTED)
async def import_knowledge(
    data: ImportKnowledge,
    current_user: User = Depends(get_current_user),
) -> dict:
    """导入知识到记忆库"""
    from services.memory import MemoryService

    memory_service = MemoryService()

    # 异步处理
    task_id = await memory_service.import_knowledge(
        user_id=str(current_user.id),
        content=data.content,
        source=data.source,
        chunk_size=data.chunk_size,
    )

    return {
        "status": "processing",
        "task_id": task_id,
        "message": "Knowledge import started",
    }

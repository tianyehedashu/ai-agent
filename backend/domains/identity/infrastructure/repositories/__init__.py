"""Identity Domain - Repository Implementations"""

from domains.identity.infrastructure.repositories.sqlalchemy_user_repository import (
    SQLAlchemyUserRepository,
)

__all__ = ["SQLAlchemyUserRepository"]

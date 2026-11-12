"""Generic async repository base class."""

from __future__ import annotations

from typing import Any, Generic, TypeVar
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from unimonitor.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Generic CRUD repository for SQLAlchemy async sessions."""

    def __init__(self, model: type[ModelType], session: AsyncSession) -> None:
        self.model = model
        self.session = session

    async def get(self, id: Any) -> ModelType | None:
        return await self.session.get(self.model, id)

    async def get_or_raise(self, id: Any) -> ModelType:
        from unimonitor.exceptions import NotFoundError
        obj = await self.get(id)
        if obj is None:
            raise NotFoundError(f"{self.model.__name__} with id '{id}' not found.")
        return obj

    async def list(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        order_by: Any = None,
        **filters: Any,
    ) -> Sequence[ModelType]:
        stmt = select(self.model)
        for attr, value in filters.items():
            if value is not None:
                stmt = stmt.where(getattr(self.model, attr) == value)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count(self, **filters: Any) -> int:
        stmt = select(func.count()).select_from(self.model)
        for attr, value in filters.items():
            if value is not None:
                stmt = stmt.where(getattr(self.model, attr) == value)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def create(self, **kwargs: Any) -> ModelType:
        obj = self.model(**kwargs)
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def update(self, obj: ModelType, **kwargs: Any) -> ModelType:
        for key, value in kwargs.items():
            setattr(obj, key, value)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def delete(self, obj: ModelType) -> None:
        await self.session.delete(obj)
        await self.session.flush()

    async def bulk_create(self, objects: list[ModelType]) -> list[ModelType]:
        self.session.add_all(objects)
        await self.session.flush()
        return objects

import uuid
from http.client import HTTPException
from typing import Any

from models.users import UserCreate, UserBase, UserUpdateMe
from core.orm import User as UserORM
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from backend.core.security import verify_password, get_password_hash


class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_user(self, user_create: UserCreate) -> UserBase:
        user_id = user_create.user_id if user_create.user_id else str(uuid.uuid4())
        db_obj = UserORM(
            user_id=user_id,
            name=user_create.name,
            password=get_password_hash(user_create.password),
            email=user_create.email,
        )
        self.session.add(db_obj)
        await self.session.commit()
        await self.session.refresh(db_obj)
        return UserBase.model_validate(db_obj, from_attributes=True)

    async def update_user(self, db_user: UserBase, user_in: UserUpdateMe) -> Any:
        stmt = select(UserORM).where(
            UserORM.user_id == db_user.user_id,
        )
        user = await self.session.scalar(stmt)
        if not user:
            raise HTTPException(404, f"User '{UserORM.user_id}' not found")

        user_update = (
            update(UserORM)
            .where(UserORM.user_id == db_user.user_id)
            .values(
                name=user_in.name if user_in.name else user.name,
                email=user_in.email if user_in.email else user.email,
            )
        )

        await self.session.execute(user_update)
        await self.session.commit()
        updated_user = await self.session.scalar(stmt)
        return updated_user

    async def get_user_by_email(self, email: str) -> UserBase | None:
        statement = select(UserORM).where(UserORM.email == email)
        session_user = await self.session.scalar(statement)
        return session_user

    async def authenticate(self, email: str, password: str) -> UserBase | None:
        db_user = await self.get_user_by_email(email=email)
        if not db_user:
            return None
        if not verify_password(password, db_user.password):
            return None
        return UserBase.model_validate(db_user, from_attributes=True)

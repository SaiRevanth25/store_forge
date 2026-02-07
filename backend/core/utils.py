from collections.abc import Generator
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core import security
from core.config import settings
from core.database import db_manager
from core.orm import User as UserORM
from models.users import TokenPayload, User

reusable_oauth2 = OAuth2PasswordBearer(tokenUrl="api/users/login/access-token")


async def get_db() -> Generator[AsyncSession, None, None]:
    async with AsyncSession(db_manager.engine) as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_db)]
TokenDep = Annotated[str, Depends(reusable_oauth2)]


async def get_current_user(session: SessionDep, token: TokenDep) -> User:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (InvalidTokenError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    stmt = select(UserORM).where(
        UserORM.user_id == token_data.sub,
    )
    user = await session.scalar(stmt)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return User.model_validate(user, from_attributes=True)
